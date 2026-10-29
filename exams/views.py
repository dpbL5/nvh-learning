from rest_framework import generics, permissions, status, pagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q, Avg, Max, Min, Count
from django.db import transaction, IntegrityError
from django.core.files.base import ContentFile
from datetime import timedelta
from classes.models import Class, ClassStudent
from .models import Question, Option, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, ImageBank, QuestionImage
from .scoring import calculate_score, score_submission, shuffle_mcq_options
from .serializers import (
    QuestionSerializer, OptionSerializer, QuizSerializer,
    QuizQuestionSerializer, QuizAttemptSerializer, QuizQuestionPublicSerializer,
    QuizAttemptReviewSerializer,
)
import hashlib
import os
import random
import uuid
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
ALLOWED_IMAGE_MIME_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'}


def _is_valid_image_bytes(data):
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                return False
            image.verify()
        return True
    except Exception:
        return False


def refresh_quiz_question_points(quiz):
    """Tính lại điểm mặc định cho đề.

    - Câu Đúng/Sai luôn cố định 1.0 điểm.
    - Câu khác chưa bị giáo viên sửa điểm: chia đều phần ngân sách còn lại
      (10 - số câu Đúng/Sai) để tổng mặc định đúng bằng 10.
    - Câu đã bị sửa điểm (is_points_overridden) giữ nguyên.
    """
    quiz_questions = list(
        QuizQuestion.objects.filter(quiz=quiz)
        .select_related('question')
        .order_by('order')
    )
    if not quiz_questions:
        return

    changed = {}

    def mark(qq):
        changed[qq.pk] = qq

    true_false_rows = [qq for qq in quiz_questions if qq.question.question_type == 'true_false']
    other_rows = [qq for qq in quiz_questions if qq.question.question_type != 'true_false']

    for qq in true_false_rows:
        if qq.points != 1.0 or qq.is_points_overridden:
            qq.points = 1.0
            qq.is_points_overridden = False
            mark(qq)

    if other_rows:
        budget = max(round(10.0 - float(len(true_false_rows)), 2), 0.0)
        default_points = round(budget / len(other_rows), 2)
        default_rows = [qq for qq in other_rows if not qq.is_points_overridden]
        has_overrides = len(default_rows) != len(other_rows)

        for index, qq in enumerate(default_rows):
            value = default_points
            if not has_overrides and index == len(default_rows) - 1:
                value = round(budget - default_points * (len(default_rows) - 1), 2)
            if qq.points != value:
                qq.points = value
                mark(qq)

    if changed:
        QuizQuestion.objects.bulk_update(list(changed.values()), ['points', 'is_points_overridden'])


class IsTeacherOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        role_name = getattr(request.user.role, 'name', None)
        return role_name in ['teacher', 'admin'] or request.user.is_superuser


def _is_admin_user(user):
    return getattr(user.role, 'name', None) == 'admin' or user.is_superuser


def _quiz_queryset_for_user(user):
    qs = Quiz.objects.select_related('classroom', 'classroom__subject', 'created_by')
    if _is_admin_user(user):
        return qs
    return (
        qs.filter(Q(created_by=user) | Q(classroom__teacher=user))
        .exclude(created_by__role__name='student')
        .distinct()
    )


def _get_owned_quiz(user, quiz_id):
    return get_object_or_404(_quiz_queryset_for_user(user), pk=quiz_id)


def _can_manage_question(user, question):
    return _is_admin_user(user) or question.created_by_id == user.id


def _delete_orphan_images(image_ids):
    if not image_ids:
        return
    from ai_core.services.cloudinary_service import cloudinary_asset_from_url, delete_from_cloudinary

    for image_bank in ImageBank.objects.filter(
        sha256__in=set(image_ids),
        questionimage__isnull=True,
    ):
        file_name = image_bank.image_file.name if image_bank.image_file else ''
        if file_name.startswith('http'):
            public_id = image_bank.cloudinary_public_id
            resource_type = 'image'
            if not public_id:
                public_id, resource_type = cloudinary_asset_from_url(file_name)
            if public_id:
                delete_from_cloudinary(public_id, resource_type or 'image')
        elif image_bank.image_file:
            try:
                image_bank.image_file.delete(save=False)
            except Exception:
                logger.exception('Failed to delete image file %s', image_bank.sha256)
        image_bank.delete()


class IsTeacherOrAdminOrStudentReadOnly(permissions.BasePermission):
    """
    Giáo viên/Admin có toàn quyền.
    Học sinh chỉ được phép xem (GET) nếu là thành viên của lớp.
    """
    def has_permission(self, request, view):
        user = request.user
        role_name = getattr(user.role, 'name', None)
        if role_name in ['teacher', 'admin'] or user.is_superuser:
            return True
        if role_name == 'student' and request.method in permissions.SAFE_METHODS:
            return True
        return False






class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ─── TEACHER / ADMIN: Question Bank CRUD ─────────────────────────────────────

class QuestionListCreateView(generics.ListCreateAPIView):
    """Giáo viên xem ngân hàng câu hỏi và tạo mới."""
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = (
            Question.objects
            .select_related('subject', 'created_by')
            .prefetch_related('options', 'question_images__image', 'question_images__uploaded_by')
            .order_by('-created_at')
        )
        subject_id = self.request.query_params.get('subject')
        difficulty = self.request.query_params.get('difficulty')
        grade = self.request.query_params.get('grade')
        q_type = self.request.query_params.get('question_type')
        search = self.request.query_params.get('search')

        if subject_id:
            try:
                subject_id = int(subject_id)
            except (TypeError, ValueError):
                return Question.objects.none()
            qs = qs.filter(subject_id=subject_id)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if grade in ('10', '11', '12'):
            qs = qs.filter(grade=grade)
        if q_type:
            qs = qs.filter(question_type=q_type)
        if search:
            qs = qs.filter(Q(text__icontains=search) | Q(context__icontains=search))
            
        status_filter = self.request.query_params.get('status')
        if status_filter == 'needs_review':
            # Logic similar to frontend isNeedsReview:
            # multiple_choice: no correct option; true_false: no statements
            # short_answer: no correct_answer_text
            q_mc = Q(question_type='multiple_choice')
            q_tf = Q(question_type='true_false')
            q_sa = Q(question_type='short_answer')
            
            qs = qs.annotate(
                correct_options_count=Count('options', filter=Q(options__is_correct=True)),
                total_options_count=Count('options')
            ).filter(
                (q_mc & Q(correct_options_count=0)) |
                (q_tf & Q(total_options_count=0)) |
                (q_sa & (Q(correct_answer_text__isnull=True) | Q(correct_answer_text='')))
            )
            
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save(created_by=request.user)

        headers = self.get_success_headers(serializer.data)
        q = self.get_queryset().get(pk=question.pk)
        return Response(QuestionSerializer(q, context={'request': request}).data, status=status.HTTP_201_CREATED, headers=headers)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = (
        Question.objects
        .select_related('subject', 'created_by')
        .prefetch_related('options', 'question_images__image', 'question_images__uploaded_by')
    )
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def update(self, request, *args, **kwargs):
        question = self.get_object()
        if not _can_manage_question(request.user, question):
            raise PermissionDenied('Bạn không có quyền sửa câu hỏi của giáo viên khác.')
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        question = self.get_object()
        if not _can_manage_question(request.user, question):
            raise PermissionDenied('Bạn không có quyền xoá câu hỏi của giáo viên khác.')
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        quiz_ids = list(
            QuizQuestion.objects.filter(question=instance)
            .values_list('quiz_id', flat=True)
            .distinct()
        )
        image_ids = list(
            QuestionImage.objects.filter(question=instance)
            .values_list('image_id', flat=True)
        )
        instance.delete()
        _delete_orphan_images(image_ids)
        for quiz in Quiz.objects.filter(id__in=quiz_ids):
            refresh_quiz_question_points(quiz)


class BulkDeleteQuestionsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def post(self, request):
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requested_ids = {int(question_id) for question_id in ids}
        except (TypeError, ValueError):
            return Response({'error': 'Danh sách ID không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)

        questions = Question.objects.filter(id__in=requested_ids)
        if not _is_admin_user(request.user):
            questions = questions.filter(created_by=request.user)

        question_ids = list(questions.values_list('id', flat=True))
        if len(question_ids) != len(requested_ids):
            return Response(
                {'error': 'Bạn chỉ có thể xoá câu hỏi do mình tạo.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        quiz_ids = list(
            QuizQuestion.objects.filter(question_id__in=question_ids)
            .values_list('quiz_id', flat=True)
            .distinct()
        )
        image_ids = list(
            QuestionImage.objects.filter(question_id__in=question_ids)
            .values_list('image_id', flat=True)
        )
        deleted_count = len(question_ids)
        Question.objects.filter(id__in=question_ids).delete()
        _delete_orphan_images(image_ids)
        for quiz in Quiz.objects.filter(id__in=quiz_ids):
            refresh_quiz_question_points(quiz)

        return Response({'message': f'Deleted {deleted_count} questions successfully'})


class OptionListCreateView(generics.ListCreateAPIView):
    serializer_class = OptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        question_id = self.kwargs.get('question_id')
        return Option.objects.filter(question_id=question_id)

    def perform_create(self, serializer):
        question = get_object_or_404(Question, pk=self.kwargs.get('question_id'))
        if not _can_manage_question(self.request.user, question):
            raise PermissionDenied('Bạn không có quyền sửa câu hỏi của giáo viên khác.')
        serializer.save(question=question)


class CloudinarySignatureView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request):
        from ai_core.services.cloudinary_service import get_upload_signature

        signature = get_upload_signature()
        if not signature:
            return Response(
                {'error': 'Cloudinary chưa được cấu hình (CLOUDINARY_API_KEY/SECRET).'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(signature)


class UploadImageView(APIView):
    """Xử lý việc upload ảnh từ Editor (ví dụ Markdown/TinyMCE) vào CSDL."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('image') or request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

        import uuid, os
        from django.conf import settings
        from ai_core.services.cloudinary_service import upload_to_cloudinary
        
        try:
            ext = os.path.splitext(file_obj.name)[1].lower()
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                return Response({"error": "Unsupported image format."}, status=status.HTTP_400_BAD_REQUEST)

            content_type = (file_obj.content_type or '').lower()
            if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES:
                return Response({"error": "Unsupported image MIME type."}, status=status.HTTP_400_BAD_REQUEST)

            file_bytes = file_obj.read()
            if not file_bytes or not _is_valid_image_bytes(file_bytes):
                return Response({"error": "Invalid image content."}, status=status.HTTP_400_BAD_REQUEST)
            file_name = f"editor_{uuid.uuid4().hex}{ext}"
            
            image_url = upload_to_cloudinary(file_bytes, file_name)
            image_url = image_url.get('secure_url') if image_url else None
            if not image_url:
                return Response({"error": "Failed to upload to cloud storage"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # API response cho TinyMCE/QuillJs typically requires { "location": "url" } or similar
            # Markdown usually expects just an URL or similar JSON
            return Response({
                "url": image_url,
                "location": image_url,  # TinyMCE
            })

        except Exception:
            logger.exception('Editor image upload failed')
            return Response({"error": "Không thể tải ảnh lên. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QuestionImageUploadView(APIView):
    """Upload ảnh cho câu hỏi, deduplicate theo SHA-256 và lưu vào ImageBank."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]
    parser_classes = [MultiPartParser]

    ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    ALLOWED_MIME_TYPES = {
        'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'
    }

    def post(self, request):
        file_obj = request.FILES.get('image') or request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No image provided.'}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return Response({'error': 'Unsupported image format.'}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (file_obj.content_type or '').lower()
        if content_type and content_type not in self.ALLOWED_MIME_TYPES:
            return Response({'error': 'Unsupported image MIME type.'}, status=status.HTTP_400_BAD_REQUEST)

        file_bytes = file_obj.read()
        if not file_bytes:
            return Response({'error': 'Image is empty.'}, status=status.HTTP_400_BAD_REQUEST)
        if not _is_valid_image_bytes(file_bytes):
            return Response({'error': 'Invalid image content.'}, status=status.HTTP_400_BAD_REQUEST)

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        relative_path = f'questions/images/bank/{sha256_hash}{ext}'

        image_bank, created = ImageBank.objects.get_or_create(
            sha256=sha256_hash,
            defaults={
                'original_filename': file_obj.name,
                'mime_type': content_type or None,
                'file_size': len(file_bytes),
            }
        )

        needs_upload = created or not image_bank.image_file
        if needs_upload:
            from ai_core.services.cloudinary_service import upload_to_cloudinary
            cloudinary_res = upload_to_cloudinary(file_bytes, file_obj.name)
            secure_url = cloudinary_res.get('secure_url') if cloudinary_res else None
            if secure_url:
                image_bank.image_file.name = secure_url
                image_bank.cloudinary_public_id = cloudinary_res.get('public_id') or image_bank.cloudinary_public_id
                image_bank.save()
            elif settings.DEBUG:
                image_bank.image_file.save(relative_path, ContentFile(file_bytes), save=True)
            else:
                if created:
                    image_bank.delete()
                return Response(
                    {'error': 'Không thể lưu ảnh lên kho lưu trữ. Vui lòng thử lại.'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        request_source_type = request.data.get('source_type', 'user_upload')
        source_type = request_source_type if request_source_type in {'ai_scan', 'user_upload', 'system'} else 'user_upload'

        question_id = request.data.get('question_id')
        question_image = None
        if question_id:
            try:
                question = Question.objects.get(pk=question_id)
            except (Question.DoesNotExist, ValueError, TypeError, ValidationError):
                return Response({'error': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)
            if not _can_manage_question(request.user, question):
                raise PermissionDenied('Bạn không có quyền sửa câu hỏi của giáo viên khác.')

            placement = request.data.get('placement', 'stem')
            try:
                position = int(request.data.get('position', 0))
            except (TypeError, ValueError):
                position = 0

            question_image, _ = QuestionImage.objects.get_or_create(
                question=question,
                image=image_bank,
                placement=placement,
                position=position,
                defaults={
                    'source_type': source_type,
                    'uploaded_by': request.user,
                    'note': request.data.get('note', ''),
                }
            )

        # Determine the correct image URL
        if image_bank.image_file and image_bank.image_file.name.startswith('http'):
            image_url = image_bank.image_file.name
        else:
            image_url = image_bank.image_file.url if image_bank.image_file else None
            if image_url and request is not None:
                image_url = request.build_absolute_uri(image_url)

        return Response({
            'sha256': image_bank.sha256,
            'url': image_url,
            'image_bank_created': created,
            'question_image_id': question_image.id if question_image else None,
            'source_type': source_type,
        }, status=status.HTTP_201_CREATED)


class QuestionImageLinkView(APIView):
    """Gắn ảnh có sẵn trong ImageBank vào câu hỏi (dùng cho AI scan hoặc tái sử dụng ảnh)."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def post(self, request, pk):
        question = get_object_or_404(Question, pk=pk)
        if not _can_manage_question(request.user, question):
            raise PermissionDenied('Bạn không có quyền sửa câu hỏi của giáo viên khác.')

        sha256_hash = request.data.get('sha256')
        if not sha256_hash:
            return Response({'error': 'sha256 is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            image_bank = ImageBank.objects.get(sha256=sha256_hash)
        except ImageBank.DoesNotExist:
            return Response({'error': 'Image not found in ImageBank.'}, status=status.HTTP_404_NOT_FOUND)

        placement = request.data.get('placement', 'stem')
        try:
            position = int(request.data.get('position', 0))
        except (TypeError, ValueError):
            position = 0

        request_source_type = request.data.get('source_type', 'ai_scan')
        source_type = request_source_type if request_source_type in {'ai_scan', 'user_upload', 'system'} else 'ai_scan'

        question_image, created = QuestionImage.objects.get_or_create(
            question=question,
            image=image_bank,
            placement=placement,
            position=position,
            defaults={
                'source_type': source_type,
                'uploaded_by': request.user,
                'note': request.data.get('note', ''),
            }
        )

        return Response({
            'question_image_id': question_image.id,
            'created': created,
            'sha256': image_bank.sha256,
            'placement': placement,
            'position': position,
            'source_type': question_image.source_type,
        })


class QuestionImageUnlinkView(APIView):
    """Gỡ liên kết ảnh khỏi câu hỏi, đồng thời xóa ảnh gốc trong ImageBank nếu không còn câu hỏi nào liên kết."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def delete(self, request, pk, qimg_id):
        try:
            qimg = QuestionImage.objects.select_related('question', 'image').get(id=qimg_id, question_id=pk)
        except QuestionImage.DoesNotExist:
            return Response({'error': 'Question image link not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_question(request.user, qimg.question):
            raise PermissionDenied('Bạn không có quyền sửa câu hỏi của giáo viên khác.')

        image_id = qimg.image_id
        qimg.delete()
        _delete_orphan_images([image_id])

        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── TEACHER / ADMIN: Quiz CRUD ─────────────────────────────────────────────

class QuizListCreateView(generics.ListCreateAPIView):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        user = self.request.user
        class_id = self.request.query_params.get('class_id')

        # Enforce class_id filter as per requirement: exams only show in their class detail
        if not class_id:
            return Quiz.objects.none()

        try:
            class_id = uuid.UUID(str(class_id))
        except (TypeError, ValueError, AttributeError):
            return Quiz.objects.none()

        return (
            _quiz_queryset_for_user(user)
            .filter(classroom_id=class_id)
            .prefetch_related('quiz_questions')
        )

    def perform_create(self, serializer):
        classroom = serializer.validated_data.get('classroom')
        if not (_is_admin_user(self.request.user) or classroom.teacher_id == self.request.user.id):
            raise PermissionDenied('Chỉ giáo viên phụ trách lớp mới có thể tạo đề thi.')
        serializer.save(created_by=self.request.user)


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminOrStudentReadOnly]

    def get_queryset(self):
        user = self.request.user
        role_name = getattr(user.role, 'name', None)
        base_qs = Quiz.objects.select_related('classroom', 'classroom__subject', 'created_by')

        if _is_admin_user(user):
            return base_qs

        if role_name == 'teacher':
            return _quiz_queryset_for_user(user)

        if role_name == 'student':
            # Students can only see published quizzes in classes they are enrolled in
            return base_qs.filter(
                classroom__class_students__student=user,
                is_published=True
            ).filter(
                Q(publish_at__isnull=True) | Q(publish_at__lte=timezone.now())
            ).filter(
                Q(assigned_to__isnull=True) | Q(assigned_to=user)
            ).distinct()

        return Quiz.objects.none()


class QuizCopyView(APIView):
    """Sao chép một đề sang một hoặc nhiều lớp của giáo viên."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def post(self, request, quiz_id):
        source = _get_owned_quiz(request.user, quiz_id)
        if source.assigned_to_id is not None:
            raise DRFValidationError({'detail': 'Không thể sao chép bài kiểm tra dành riêng cho một học sinh.'})
        classroom_ids = request.data.get('classroom_ids') or []
        if not isinstance(classroom_ids, list) or not classroom_ids:
            raise DRFValidationError({'classroom_ids': 'Chọn ít nhất một lớp.'})

        suffix = request.data.get('title_suffix')
        suffix = ' (bản sao)' if suffix is None else str(suffix)[:50]

        source_questions = list(
            source.quiz_questions.select_related('question').order_by('order')
        )

        created = []
        skipped = []
        seen = set()

        for raw_id in classroom_ids:
            try:
                classroom_id = uuid.UUID(str(raw_id))
            except (TypeError, ValueError, AttributeError):
                skipped.append({'classroom_id': str(raw_id), 'reason': 'invalid_id'})
                continue
            if classroom_id in seen:
                continue
            seen.add(classroom_id)

            classroom = Class.objects.filter(pk=classroom_id).first()
            if classroom is None:
                skipped.append({'classroom_id': str(classroom_id), 'reason': 'not_found'})
                continue
            if not (_is_admin_user(request.user) or classroom.teacher_id == request.user.id):
                skipped.append({'classroom_id': str(classroom_id), 'reason': 'permission_denied'})
                continue

            with transaction.atomic():
                copied_quiz = Quiz.objects.create(
                    title=(source.title + suffix)[:255],
                    description=source.description,
                    classroom=classroom,
                    duration_minutes=source.duration_minutes,
                    is_published=False,
                    publish_at=None,
                    due_date=None,
                    assigned_to=None,
                    created_by=request.user,
                )
                QuizQuestion.objects.bulk_create([
                    QuizQuestion(
                        quiz=copied_quiz,
                        question=quiz_question.question,
                        order=quiz_question.order,
                        points=quiz_question.points,
                        is_points_overridden=quiz_question.is_points_overridden,
                    )
                    for quiz_question in source_questions
                ])
            created.append(copied_quiz)

        if not created:
            return Response(
                {'created': [], 'skipped': skipped},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = QuizSerializer(created, many=True, context={'request': request})
        return Response(
            {'created': serializer.data, 'skipped': skipped},
            status=status.HTTP_201_CREATED,
        )


class QuizQuestionListCreateView(generics.ListCreateAPIView):
    serializer_class = QuizQuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        quiz = _get_owned_quiz(self.request.user, self.kwargs.get('quiz_id'))
        return (
            QuizQuestion.objects
            .filter(quiz=quiz)
            .select_related('question', 'quiz')
            .prefetch_related('question__options', 'question__question_images__image', 'question__question_images__uploaded_by')
        )

    def perform_create(self, serializer):
        quiz = _get_owned_quiz(self.request.user, self.kwargs.get('quiz_id'))
        try:
            with transaction.atomic():
                quiz_question = serializer.save(quiz=quiz, points=0.0, is_points_overridden=False)
        except IntegrityError:
            raise DRFValidationError({'detail': 'Câu hỏi này đã có trong đề.'})
        refresh_quiz_question_points(quiz)
        quiz_question.refresh_from_db()


class QuizQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = QuizQuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        return (
            QuizQuestion.objects
            .filter(quiz__in=_quiz_queryset_for_user(self.request.user))
            .select_related('question', 'quiz')
            .prefetch_related('question__options', 'question__question_images__image', 'question__question_images__uploaded_by')
        )

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                quiz_question = serializer.save()
        except IntegrityError:
            raise DRFValidationError({'detail': 'Câu hỏi này đã có trong đề.'})
        if (
            quiz_question.question.question_type != 'true_false'
            and 'points' in self.request.data
        ):
            quiz_question.is_points_overridden = True
            quiz_question.save(update_fields=['is_points_overridden'])
        refresh_quiz_question_points(quiz_question.quiz)
        quiz_question.refresh_from_db()

    def perform_destroy(self, instance):
        quiz = instance.quiz
        instance.delete()
        refresh_quiz_question_points(quiz)


class QuizQuestionResetPointsView(APIView):
    """Bỏ điểm tự sửa của một câu, quay về mặc định của đề."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def post(self, request, quiz_id, pk):
        quiz = _get_owned_quiz(request.user, quiz_id)
        quiz_question = get_object_or_404(
            QuizQuestion.objects.select_related('question', 'quiz'),
            pk=pk,
            quiz=quiz,
        )
        quiz_question.is_points_overridden = False
        quiz_question.save(update_fields=['is_points_overridden'])
        refresh_quiz_question_points(quiz)
        quiz_question.refresh_from_db()
        return Response(QuizQuestionSerializer(quiz_question, context={'request': request}).data)


# ─── STUDENT: Take Exam ─────────────────────────────────────────────────────

class StudentQuizListView(generics.ListAPIView):
    serializer_class = QuizSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user.role, 'name', None) != 'student':
            return Quiz.objects.none()
            
        class_id = self.request.query_params.get('class_id')
        if not class_id:
            return Quiz.objects.none()

        try:
            class_id = uuid.UUID(str(class_id))
        except (TypeError, ValueError, AttributeError):
            return Quiz.objects.none()

        return Quiz.objects.filter(
            classroom_id=class_id,
            classroom__class_students__student=user, 
            is_published=True
        ).prefetch_related('quiz_questions').filter(
            Q(publish_at__isnull=True) | Q(publish_at__lte=timezone.now())
        ).filter(
            Q(assigned_to__isnull=True) | Q(assigned_to=user)
        )


class QuizStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, quiz_id):
        user = request.user
        try:
            quiz = Quiz.objects.get(id=quiz_id, is_published=True)
        except Quiz.DoesNotExist:
            return Response(
                {'detail': 'Đề thi không tồn tại hoặc chưa được mở.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not quiz.classroom.class_students.filter(student=user).exists():
            return Response({'detail': 'Bạn không thuộc lớp học này.'}, status=status.HTTP_403_FORBIDDEN)

        if quiz.assigned_to and quiz.assigned_to != user:
            return Response({'detail': 'Bài kiểm tra này không dành cho bạn.'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        if quiz.publish_at and quiz.publish_at > now:
            return Response(
                {'detail': 'Đề thi chưa đến giờ công khai.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if quiz.due_date and quiz.due_date < now:
            return Response(
                {'detail': 'Đề thi đã quá hạn nộp bài.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        attempt, created = QuizAttempt.objects.get_or_create(quiz=quiz, student=user)
        if attempt.is_completed:
            serializer = QuizAttemptReviewSerializer(attempt, context={'request': request})
            return Response(serializer.data)

        questions = list(
            QuizQuestion.objects
            .filter(quiz=quiz)
            .select_related('question')
            .prefetch_related('question__options', 'question__question_images__image', 'question__question_images__uploaded_by')
        )
        # Xáo trộn ổn định theo lượt thi: mỗi học sinh có thứ tự khác nhau,
        # nhưng tải lại trang trong cùng lượt vẫn giữ nguyên thứ tự.
        random.Random(attempt.pk).shuffle(questions)
        for quiz_question in questions:
            shuffle_mcq_options(quiz_question, attempt.pk)
        serializer = QuizQuestionPublicSerializer(questions, many=True)

        return Response({
            'attempt_id': attempt.id,
            'duration_minutes': quiz.duration_minutes,
            'start_time': attempt.start_time,
            'questions': serializer.data,
        })


class QuizSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        user = request.user
        try:
            attempt = QuizAttempt.objects.select_related('quiz').get(id=attempt_id, student=user)
        except QuizAttempt.DoesNotExist:
            return Response({'detail': 'Lượt thi không tồn tại.'}, status=status.HTTP_404_NOT_FOUND)

        if attempt.is_completed:
            return Response({'detail': 'Bài này đã được nộp.'}, status=status.HTTP_400_BAD_REQUEST)

        quiz = attempt.quiz
        now = timezone.now()
        if quiz.due_date and now > quiz.due_date:
            return Response({'detail': 'Đề thi đã quá hạn nộp bài.'}, status=status.HTTP_400_BAD_REQUEST)
        if attempt.start_time + timedelta(minutes=quiz.duration_minutes) + timedelta(seconds=60) < now:
            return Response({'detail': 'Đã hết thời gian làm bài.'}, status=status.HTTP_400_BAD_REQUEST)

        answers_data = request.data.get('answers', [])
        if not isinstance(answers_data, list):
            return Response({'detail': 'Dữ liệu câu trả lời không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(answers_data) > 500:
            return Response({'detail': 'Số lượng câu trả lời vượt quá giới hạn.'}, status=status.HTTP_400_BAD_REQUEST)

        answers_by_question = {}
        for answer in answers_data:
            if not isinstance(answer, dict):
                continue
            try:
                qq_id = int(answer.get('quiz_question_id'))
            except (TypeError, ValueError):
                continue
            answers_by_question.setdefault(qq_id, []).append(answer)

        with transaction.atomic():
            attempt = QuizAttempt.objects.select_for_update().select_related('quiz').get(pk=attempt.pk)
            if attempt.is_completed:
                return Response({'detail': 'Bài này đã được nộp.'}, status=status.HTTP_400_BAD_REQUEST)

            attempt.answers.all().delete()

            quiz_questions = list(
                QuizQuestion.objects
                .filter(quiz=quiz)
                .select_related('question')
                .prefetch_related('question__options')
            )
            decisions, earned_points, total_points = score_submission(
                quiz_questions, answers_by_question,
            )
            for decision in decisions:
                StudentAnswer.objects.create(
                    attempt=attempt,
                    quiz_question=decision['quiz_question'],
                    selected_option=decision['selected_option'],
                    answer_text=decision['answer_text'],
                    answer_value=decision['answer_value'],
                )

            attempt.score = calculate_score(earned_points, total_points)
            attempt.is_completed = True
            attempt.end_time = now
            attempt.save(update_fields=['score', 'is_completed', 'end_time'])

        serializer = QuizAttemptReviewSerializer(attempt, context={'request': request})
        return Response(serializer.data)





# ─── ANALYTICS ───────────────────────────────────────────────────────────────

class ClassAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, class_id):
        try:
            classroom = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            return Response({"error": "Lớp học không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        if not (_is_admin_user(request.user) or classroom.teacher_id == request.user.id):
            return Response({"error": "Bạn không có quyền xem thống kê lớp này."}, status=status.HTTP_403_FORBIDDEN)

        quizzes = Quiz.objects.filter(classroom=classroom).exclude(created_by__role__name='student')
        analytics = {
            "class_name": classroom.name,
            "total_quizzes": quizzes.count(),
            "quizzes": [],
        }

        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(quiz=quiz, is_completed=True)
            if not attempts.exists():
                continue

            stats = attempts.aggregate(
                avg_score=Avg('score'), max_score=Max('score'), min_score=Min('score'),
            )

            q_stats = []
            quiz_qs = list(
                QuizQuestion.objects.filter(quiz=quiz).select_related('question')
            )
            answers = (
                StudentAnswer.objects
                .filter(attempt__quiz=quiz, attempt__is_completed=True)
                .select_related('quiz_question', 'selected_option', 'quiz_question__question')
            )
            answer_stats = {}
            for answer in answers:
                entry = answer_stats.setdefault(answer.quiz_question_id, {'total': 0, 'correct': 0})
                entry['total'] += 1
                if answer.is_correct():
                    entry['correct'] += 1

            for qq in quiz_qs:
                entry = answer_stats.get(qq.id)
                if not entry or entry['total'] == 0:
                    continue
                accuracy = (entry['correct'] / entry['total']) * 100
                q_stats.append({
                    "question_text": (qq.question.text or '')[:100],
                    "accuracy": round(accuracy, 1),
                })

            q_stats.sort(key=lambda x: x['accuracy'])
            trouble_questions = q_stats[:3]

            analytics["quizzes"].append({
                "quiz_title": quiz.title,
                "average_score": round(stats['avg_score'], 2) if stats['avg_score'] else 0,
                "max_score": stats['max_score'],
                "min_score": stats['min_score'],
                "total_attempts": attempts.count(),
                "trouble_questions": trouble_questions,
            })

        return Response(analytics)


class TeacherAdminProgressAPIView(APIView):
    """Analytics for teacher/admin showing class quiz average scores."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request):
        user = request.user
        role_name = getattr(user.role, 'name', None)

        if role_name == 'teacher':
            quizzes = Quiz.objects.filter(classroom__teacher=user)
        else:
            quizzes = Quiz.objects.all()
        quizzes = quizzes.exclude(created_by__role__name='student')

        attempts = QuizAttempt.objects.filter(quiz__in=quizzes, is_completed=True)
        if not attempts.exists():
            return Response({'quizzes': []})

        quiz_stats = (
            attempts
            .values('quiz_id', 'quiz__title', 'quiz__classroom__name')
            .annotate(
                average_score=Avg('score'),
                total_attempts=Count('id'),
                last_attempt=Max('end_time')
            )
            .order_by('-last_attempt')[:20]
        )

        results = []
        for item in quiz_stats:
            results.append({
                'quiz_id': item['quiz_id'],
                'quiz_title': item['quiz__title'],
                'class_name': item['quiz__classroom__name'] or '',
                'average_score': round(item['average_score'] or 0, 2),
                'total_attempts': item['total_attempts'],
                'last_attempt': item['last_attempt'].isoformat() if item['last_attempt'] else None,
            })

        return Response({'quizzes': results})


class StudentProgressAPIView(APIView):
    """API for both students (viewing themselves) and teachers (viewing a specific student)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        target_student_id = request.query_params.get('student_id')
        class_id = request.query_params.get('class_id')

        user = request.user
        role_name = getattr(user.role, 'name', None)
        is_admin = _is_admin_user(user)

        classroom = None
        if class_id:
            try:
                classroom = Class.objects.get(id=class_id)
            except (Class.DoesNotExist, ValidationError, ValueError):
                return Response({"error": "Lớp học không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        if role_name == 'student':
            student = user
        elif role_name == 'teacher' or is_admin:
            if not target_student_id:
                return Response({"error": "student_id is required cho giáo viên/quản trị."}, status=status.HTTP_400_BAD_REQUEST)
            from accounts.models import User
            try:
                student = User.objects.get(id=target_student_id)
            except (User.DoesNotExist, ValidationError, ValueError):
                return Response({"error": "Học sinh không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

            if not is_admin:
                if classroom:
                    if classroom.teacher_id != user.id:
                        return Response({'error': 'Bạn không có quyền xem tiến độ của học sinh lớp này.'}, status=status.HTTP_403_FORBIDDEN)
                elif not ClassStudent.objects.filter(student=student, classroom__teacher=user).exists():
                    return Response({'error': 'Bạn không có quyền xem tiến độ của học sinh này.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'error': 'Bạn không có quyền xem tiến độ học tập.'}, status=status.HTTP_403_FORBIDDEN)

        # Query completed attempts
        attempts = QuizAttempt.objects.filter(student=student, is_completed=True)
        if not is_admin and role_name == 'teacher':
            attempts = (
                attempts
                .filter(quiz__classroom__teacher=user)
                .exclude(quiz__created_by__role__name='student')
            )
        if classroom:
            attempts = attempts.filter(quiz__classroom=classroom)

        attempts = attempts.select_related('quiz').order_by('end_time')
        
        # Build timeline
        timeline = []
        for att in attempts:
            if att.end_time:
                timeline.append({
                    "date": att.end_time.isoformat(),
                    "quiz_title": att.quiz.title,
                    "score": att.score
                })
                
        # Build weaknesses analysis
        subject_stats = {}
        difficulty_stats = {}

        # ── Phân tích toàn bộ lịch sử ──────────────────────────────
        answers = StudentAnswer.objects.filter(attempt__in=attempts).select_related('quiz_question__question', 'quiz_question__question__subject')
        
        for ans in answers:
            q = ans.quiz_question.question
            subj_name = q.subject.name if q.subject else "Chung"
            diff = q.difficulty
            
            is_corr = ans.is_correct()
            
            if subj_name not in subject_stats:
                subject_stats[subj_name] = {'total': 0, 'correct': 0}
            subject_stats[subj_name]['total'] += 1
            if is_corr:
                subject_stats[subj_name]['correct'] += 1
                
            if diff not in difficulty_stats:
                difficulty_stats[diff] = {'total': 0, 'correct': 0}
            difficulty_stats[diff]['total'] += 1
            if is_corr:
                difficulty_stats[diff]['correct'] += 1
                
        weaknesses = []
        for subj, stats in subject_stats.items():
            if stats['total'] >= 3: # Min questions to determine weakness
                acc = stats['correct'] / stats['total']
                if acc < 0.6: # Less than 60% accuracy is considered a weakness
                    weaknesses.append(f"Môn {subj} (Chính xác {int(acc*100)}%)")
                    
        diff_map = {'easy': 'Nhận biết', 'medium': 'Thông hiểu', 'hard': 'Vận dụng'}
        for diff, stats in difficulty_stats.items():
            if stats['total'] >= 3:
                acc = stats['correct'] / stats['total']
                if acc < 0.6:
                    weaknesses.append(f"Kỹ năng {diff_map.get(diff, diff)} (Chính xác {int(acc*100)}%)")

        # ── Phân tích bài thi GẦN NHẤT (bắt điểm yếu mới phát sinh) ──
        recent_attempt = attempts.last()
        if recent_attempt:
            recent_subject_stats = {}
            recent_diff_stats = {}
            recent_answers = StudentAnswer.objects.filter(attempt=recent_attempt).select_related(
                'quiz_question__question', 'quiz_question__question__subject'
            )
            for ans in recent_answers:
                q = ans.quiz_question.question
                subj_name = q.subject.name if q.subject else "Chung"
                diff = q.difficulty
                is_corr = ans.is_correct()

                if subj_name not in recent_subject_stats:
                    recent_subject_stats[subj_name] = {'total': 0, 'correct': 0}
                recent_subject_stats[subj_name]['total'] += 1
                if is_corr:
                    recent_subject_stats[subj_name]['correct'] += 1

                if diff not in recent_diff_stats:
                    recent_diff_stats[diff] = {'total': 0, 'correct': 0}
                recent_diff_stats[diff]['total'] += 1
                if is_corr:
                    recent_diff_stats[diff]['correct'] += 1

            # Đánh dấu yếu từ bài gần nhất (ngưỡng thấp hơn: ≥1 câu, accuracy < 70%)
            for subj, st in recent_subject_stats.items():
                if st['total'] >= 1:
                    acc = st['correct'] / st['total']
                    if acc < 0.7:
                        label = f"Môn {subj} (Bài gần nhất: {int(acc*100)}%)"
                        if label not in weaknesses:
                            weaknesses.append(label)

            for diff, st in recent_diff_stats.items():
                if st['total'] >= 1:
                    acc = st['correct'] / st['total']
                    if acc < 0.7:
                        label = f"Kỹ năng {diff_map.get(diff, diff)} (Bài gần nhất: {int(acc*100)}%)"
                        if label not in weaknesses:
                            weaknesses.append(label)

        # ── Phát hiện SỤT ĐIỂM mạnh giữa các bài ──────────────────
        score_trend = None
        score_decline_warning = None
        timeline_scores = [t['score'] for t in timeline if t['score'] is not None]
        if len(timeline_scores) >= 2:
            last_score = timeline_scores[-1]
            prev_score = timeline_scores[-2]
            drop = prev_score - last_score
            if drop >= 3:
                score_decline_warning = (
                    f"Điểm sụt mạnh: từ {prev_score} xuống {last_score} "
                    f"(giảm {drop:.1f} điểm so với bài trước)"
                )
                if score_decline_warning not in weaknesses:
                    weaknesses.insert(0, score_decline_warning)
            if last_score > prev_score:
                score_trend = "up"
            elif last_score < prev_score:
                score_trend = "down"
            else:
                score_trend = "stable"

        return Response({
            "timeline": timeline,
            "weaknesses": weaknesses,
            "score_trend": score_trend,
            "student_name": getattr(student, 'full_name', '') or student.username,
            "total_completed": attempts.count()
        })

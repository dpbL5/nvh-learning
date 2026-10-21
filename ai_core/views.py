import os
import json
import zipfile
import tempfile
import docx
import hashlib
import re
import math
import logging

from django.conf import settings
from django.core.cache import cache
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from pgvector.django import L2Distance

from .models import DocumentChunk, Document, ClassInsight
from classes.models import Class
from .serializers import DocumentSerializer
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework import permissions
from exams.models import Question, Option, Quiz, QuizQuestion
from exams.views import (
    IsTeacherOrAdmin,
    _get_owned_quiz,
    rebalance_quiz_question_points,
)
from .services.ai_generator import AIGeneratorService, NoQuestionsGenerated
from .services.ai_provider import get_client
from .services.cloudinary_service import (
    cloudinary_asset_from_url,
    delete_from_cloudinary,
    is_allowed_remote_url,
)
from django.utils import timezone
from datetime import timedelta

AI_TUTOR_MODEL = os.environ.get('AI_TUTOR_MODEL_NAME', 'gpt-4.1')
AI_EXTRACTION_MODEL = os.environ.get('AI_EXTRACTION_MODEL_NAME', 'gpt-4.1')
MAX_REMOTE_FILE_BYTES = 25 * 1024 * 1024
try:
    INSIGHT_COOLDOWN_DAYS = max(0, int(os.environ.get('AI_INSIGHT_COOLDOWN_DAYS', '5')))
except (TypeError, ValueError):
    INSIGHT_COOLDOWN_DAYS = 5
AI_THROTTLE_CLASSES = [] if settings.RUNNING_TESTS else [ScopedRateThrottle]
ai_client = get_client()
logger = logging.getLogger(__name__)


def _get_class_for_user(user, class_id, allow_student=False):
    try:
        classroom = Class.objects.get(id=class_id)
    except (Class.DoesNotExist, DjangoValidationError, ValueError):
        raise Http404('Lớp học không tồn tại.')

    role_name = getattr(user.role, 'name', None)
    if role_name == 'admin' or user.is_superuser:
        return classroom
    if role_name == 'teacher' and classroom.teacher_id == user.id:
        return classroom
    if allow_student and role_name == 'student' and classroom.class_students.filter(student=user).exists():
        return classroom
    raise PermissionDenied('Bạn không có quyền truy cập lớp học này.')

class RAGChatbotView(APIView):
    """
    API Chatbot sử dụng kiến trúc RAG tích hợp file docx giảng dạy của nhà trường.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_chat'

    @staticmethod
    def _make_chat_cache_key(class_id, question):
        normalized_question = re.sub(r'\s+', ' ', str(question or '')).strip().lower()
        digest = hashlib.sha256(f"{class_id}|{normalized_question}".encode('utf-8')).hexdigest()
        return f"ai_tro_giang:chat:{digest}"

    def post(self, request):
        if not ai_client.is_configured():
            return Response({"error": "Chưa cấu hình AI API key trên server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        class_id = request.data.get('class_id')
        question = request.data.get('question')

        if not class_id or not question:
            raise ValidationError("Vui lòng gửi đầy đủ 'class_id' và 'question'.")
        if len(str(question)) > 2000:
            return Response({"error": "Câu hỏi quá dài."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Rate Limiting: 1 minute per question ---
        user_id = request.user.id
        cache_key = f"ai_tro_giang_last_chat_{user_id}"
        last_chat_time = cache.get(cache_key)
        
        if last_chat_time:
            wait_seconds = int(60 - (time.time() - last_chat_time))
            if wait_seconds > 0:
                return Response({
                    "error": f"Vui lòng đợi {wait_seconds} giây trước khi gửi câu hỏi tiếp theo.",
                    "wait_seconds": wait_seconds
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Set new timestamp in cache
        cache.set(cache_key, time.time(), timeout=60)

        try:
            # Xác thực user có quyền vào lớp không
            _get_class_for_user(request.user, class_id, allow_student=True)
        except Http404:
            return Response({"error": "Lớp học không tồn tại."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied:
            return Response({"error": "Bạn không có quyền truy cập lớp này!"}, status=status.HTTP_403_FORBIDDEN)

        try:
            response_cache_key = self._make_chat_cache_key(class_id=class_id, question=question)
            cached_answer = cache.get(response_cache_key)
            if isinstance(cached_answer, dict):
                return Response(cached_answer)

            # CẬP NHẬT: Gọi AIGeneratorService Optimize NotebookLM RAG
            chatbot_answer = AIGeneratorService.chat_with_tutor(class_id, question)
            
            payload = {
                "answer": chatbot_answer,
                "sources": []
            }
            cache.set(response_cache_key, payload, timeout=180)

            return Response(payload)

        except Exception:
            logger.exception('RAG chat failed')
            return Response({"error": "Lỗi AI Core. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AIClassInsightView(APIView):
    """
    Quản lý báo cáo AI Insight của lớp học.
    - GET: Lấy báo cáo hiện tại, kèm thông tin có được phép tạo mới không (5 ngày/lần).
    - POST: Yêu cầu tạo báo cáo mới (nếu đủ điều kiện).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def _check_permission(self, request):
        role_name = getattr(request.user.role, 'name', None)
        if role_name not in ['teacher', 'admin'] and not request.user.is_superuser:
            raise PermissionDenied("Chỉ giáo viên mới có quyền xem báo cáo AI Insight.")

    def _cooldown_state(self, insight):
        if not insight or INSIGHT_COOLDOWN_DAYS <= 0:
            return True, 0
        next_at = insight.updated_at + timedelta(days=INSIGHT_COOLDOWN_DAYS)
        now = timezone.now()
        if now >= next_at:
            return True, 0
        days_remaining = max(1, math.ceil((next_at - now).total_seconds() / 86400))
        return False, days_remaining

    def get(self, request):
        self._check_permission(request)
        class_id = request.query_params.get('class_id')
        if not class_id:
            return Response({"error": "Thiếu class_id."}, status=status.HTTP_400_BAD_REQUEST)

        _get_class_for_user(request.user, class_id)

        insight = ClassInsight.objects.filter(classroom_id=class_id).first()
        can_generate, days_remaining = self._cooldown_state(insight)
        if not insight:
            return Response({
                "insight": None,
                "can_generate": True,
                "days_remaining": 0
            })
        return Response({
            "insight": insight.content,
            "updated_at": insight.updated_at,
            "can_generate": can_generate,
            "days_remaining": days_remaining
        })

    def post(self, request):
        self._check_permission(request)
        
        class_id = request.data.get('class_id')
        data = request.data.get('analytics_data')
        class_name = str(request.data.get('class_name') or 'Lớp học')[:200]

        if not class_id or not data:
            return Response({"error": "Thiếu class_id hoặc dữ liệu phân tích."}, status=status.HTTP_400_BAD_REQUEST)
        if len(json.dumps(data, ensure_ascii=False)) > 20000:
            return Response({"error": "Dữ liệu phân tích quá lớn."}, status=status.HTTP_400_BAD_REQUEST)

        _get_class_for_user(request.user, class_id)

        existing_insight = ClassInsight.objects.filter(classroom_id=class_id).first()
        can_generate, days_remaining = self._cooldown_state(existing_insight)
        if not can_generate:
            return Response({
                "error": f"Báo cáo AI chỉ có thể tạo mới sau {days_remaining} ngày.",
                "can_generate": False,
                "days_remaining": days_remaining,
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            system_prompt = f"""
Bạn là chuyên gia phân tích giáo dục của NVH Learning. 
Hãy phân tích dữ liệu kết quả học tập của lớp {class_name} dưới đây và đưa ra báo cáo ngắn gọn, súc tích.

DỮ LIỆU THỐNG KÊ:
{json.dumps(data, indent=2, ensure_ascii=False)}

YÊU CẦU BÁO CÁO:
1. Nhận xét tổng quan về phổ điểm (Khá, Giỏi, Trung bình).
2. Chỉ ra các "Lỗ hổng kiến thức" - những câu hỏi hoặc chủ đề mà nhiều học sinh làm sai nhất. Đưa ra nguyên nhân có thể dạng giả thuyết.
3. Đề xuất hành động cho giáo viên (ví dụ: cần ôn lại chương nào, khen thưởng nhóm học sinh nào).
4. SỬ DỤNG MARKDOWN:
   - Dùng heading (#, ##, ###) để phân chia cấu trúc rõ ràng.
   - Dùng in đậm (**text**) cho các ý chính.
   - Viết các công thức (nếu có) bằng định dạng LaTeX (ví dụ: $E=mc^2$ hoặc $$x = \\frac{{-b \\pm \\sqrt{{\\Delta}}}}{{2a}}$$).
   - Ngôn ngữ chuyên nghiệp, khuyến khích.

BÁO CÁO:
"""
            response = ai_client.generate_content(system_prompt)

            # Cập nhật đè lên database
            insight, created = ClassInsight.objects.update_or_create(
                classroom_id=class_id,
                defaults={'content': response.text}
            )
            can_generate, days_remaining = self._cooldown_state(insight)

            return Response({
                "insight": insight.content,
                "updated_at": insight.updated_at,
                "can_generate": can_generate,
                "days_remaining": days_remaining
            })
        except Exception:
            logger.exception('AI insight generation failed')
            return Response({"error": "Lỗi AI Insight. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClassDocumentListView(APIView):
    """Lấy danh sách tài liệu RAG của một lớp học."""
    permission_classes = [IsAuthenticated]

    def get(self, request, class_id):
        classroom = _get_class_for_user(request.user, class_id, allow_student=True)

        docs = Document.objects.filter(classroom=classroom).order_by('-uploaded_at')
        serializer = DocumentSerializer(docs, many=True)
        return Response(serializer.data)

class UploadClassDocumentView(APIView):
    """Giáo viên upload tài liệu, dùng Gemini bóc tách văn bản và tạo Vector Embeddings lưu vào DB."""
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def post(self, request, class_id):
        user = request.user
        role_name = getattr(user.role, 'name', None)
        if role_name not in ['teacher', 'admin'] and not user.is_superuser:
            return Response({"error": "Chỉ giáo viên mới có quyền upload tài liệu RAG."}, status=status.HTTP_403_FORBIDDEN)

        try:
            classroom = _get_class_for_user(user, class_id)
        except Http404:
            return Response({"error": "Lớp học không tồn tại."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied:
            return Response({"error": "Bạn không có quyền upload tài liệu cho lớp này."}, status=status.HTTP_403_FORBIDDEN)

        file_obj = request.FILES.get('file')
        file_url = request.data.get('file_url')
        file_name = str(request.data.get('file_name') or 'document.pdf')[:255]

        if not file_obj and not file_url:
            return Response({"error": "Vui lòng đính kèm file hoặc gửi đường dẫn file (file_url)."}, status=status.HTTP_400_BAD_REQUEST)

        if file_obj and file_obj.size > MAX_REMOTE_FILE_BYTES:
            return Response({"error": "Tài liệu vượt quá dung lượng cho phép."}, status=status.HTTP_400_BAD_REQUEST)

        if file_url and not is_allowed_remote_url(file_url):
            return Response({"error": "Đường dẫn tài liệu không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        tmp_file_path = None
        final_public_id = None
        final_resource_type = 'raw'
        try:
            if file_obj:
                ext = os.path.splitext(file_obj.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                    for chunk in file_obj.chunks():
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name

                # Upload lên Cloudinary trước khi tạo record Document (nếu client không tự upload)
                from .services.cloudinary_service import upload_to_cloudinary
                cloudinary_res = upload_to_cloudinary(tmp_file_path, file_name=file_obj.name, resource_type='raw')
                
                final_file_url = cloudinary_res.get('secure_url') if cloudinary_res else None
                final_public_id = cloudinary_res.get('public_id') if cloudinary_res else None
                final_file_name = file_obj.name
            else:
                # Client đã tự upload lên Cloudinary (bypass Vercel 4.5MB limit)
                import requests
                ext = os.path.splitext(file_name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                    resp = requests.get(file_url, stream=True, timeout=30, allow_redirects=False)
                    resp.raise_for_status()
                    total_bytes = 0
                    for chunk in resp.iter_content(chunk_size=8192):
                        total_bytes += len(chunk)
                        if total_bytes > MAX_REMOTE_FILE_BYTES:
                            raise ValueError('Tài liệu vượt quá dung lượng cho phép.')
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name
                final_file_url = file_url
                final_public_id, derived_resource_type = cloudinary_asset_from_url(file_url)
                final_resource_type = derived_resource_type or 'raw'
                final_file_name = file_name

            doc_obj = Document.objects.create(
                classroom=classroom,
                title=final_file_name,
                file_url=final_file_url,
                cloudinary_public_id=final_public_id
            )

            try:
                extraction_result = AIGeneratorService.ingest_document(tmp_file_path, doc_obj.id)
                os.remove(tmp_file_path)
                
                serializer = DocumentSerializer(doc_obj)
                response_data = serializer.data
                response_data['knowledge_chunks_count'] = extraction_result.get('knowledge_chunks_count', 0)
                response_data['questions_extracted'] = len(extraction_result.get('questions', []))
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            except Exception as ai_err:
                # Nếu lỗi trích xuất AI, xoá cả bản ghi DB và file trên Cloudinary
                logger.exception('Document ingestion failed: %s', ai_err)
                if doc_obj.cloudinary_public_id:
                    delete_from_cloudinary(doc_obj.cloudinary_public_id, resource_type=final_resource_type)
                doc_obj.delete()
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
                return Response({"error": "Lỗi xử lý hệ thống AI. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception('Document upload failed: %s', e)
            if final_public_id:
                delete_from_cloudinary(final_public_id, resource_type=final_resource_type)
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except Exception:
                    pass
            return Response({"error": "Lỗi upload tài liệu. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteClassDocumentView(APIView):
    """Giáo viên xoá tài liệu RAG, các chunks tự động cascade."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, doc_id):
        user = request.user
        role_name = getattr(user.role, 'name', None)
        if role_name not in ['teacher', 'admin'] and not user.is_superuser:
            return Response({"error": "Chỉ giáo viên mới có quyền xoá tài liệu."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            doc = Document.objects.select_related('classroom').get(id=doc_id)
        except Document.DoesNotExist:
            return Response({"error": "Không tìm thấy tài liệu."}, status=status.HTTP_404_NOT_FOUND)

        _get_class_for_user(user, doc.classroom_id)

        if doc.cloudinary_public_id:
            delete_from_cloudinary(doc.cloudinary_public_id, resource_type='raw')

        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── AI QUESTION GENERATOR VIEWS ────────────────────────────────────────────

class AIExtractFromFileView(APIView):
    """Nhận file upload hoặc URL, trích xuất câu hỏi qua AI."""
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        files_data = request.data.get('files')
        file_obj = request.FILES.get('file')
        file_url = request.data.get('file_url')
        file_name = str(request.data.get('file_name') or 'downloaded_file.docx')[:255]
        subject_id = request.data.get('subject_id')
        subject_name = ""

        if file_obj and file_obj.size > MAX_REMOTE_FILE_BYTES:
            return Response({"error": "Tài liệu vượt quá dung lượng cho phép."}, status=status.HTTP_400_BAD_REQUEST)
        
        if subject_id:
            try:
                from classes.models import Subject
                subject_name = Subject.objects.get(id=subject_id).name
            except Exception:
                pass

        import tempfile
        import os
        to_process = []
        if files_data and isinstance(files_data, list):
            if len(files_data) > 10:
                return Response({"error": "Số lượng tệp vượt quá giới hạn."}, status=status.HTTP_400_BAD_REQUEST)
            to_process = files_data
        elif file_url:
            to_process.append({'file_url': file_url, 'file_name': file_name})
        elif file_obj:
            to_process.append({'file_obj': file_obj})

        if not to_process:
            return Response({"error": "No files provided."}, status=status.HTTP_400_BAD_REQUEST)

        for item in to_process:
            if not isinstance(item, dict):
                return Response({"error": "Dữ liệu file không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
            file_url_to_check = item.get('file_url')
            if file_url_to_check and not is_allowed_remote_url(file_url_to_check):
                return Response({"error": "Đường dẫn file không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_assets = []
        if files_data and isinstance(files_data, list):
            for item in files_data:
                if isinstance(item, dict):
                    public_id, resource_type = cloudinary_asset_from_url(item.get('file_url'))
                    if public_id:
                        uploaded_assets.append((public_id, resource_type or 'image'))

        import requests
        import mimetypes
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http_session = requests.Session()
        http_session.mount("https://", adapter)
        http_session.mount("http://", adapter)

        all_questions = []
        all_images_map = {}

        try:
            for item in to_process:
                tmp_file_path = None
                try:
                    target_file_obj = item.get('file_obj')
                    target_file_url = item.get('file_url')
                    target_file_name = item.get('file_name', 'downloaded.docx')

                    if target_file_obj:
                        ext = os.path.splitext(target_file_obj.name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                            for chunk in target_file_obj.chunks():
                                tmp_file.write(chunk)
                            tmp_file_path = tmp_file.name
                        mime_type = target_file_obj.content_type
                    elif target_file_url:
                        ext = os.path.splitext(target_file_name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                            # Use custom session with retries and timeout
                            resp = http_session.get(target_file_url, stream=True, timeout=30, allow_redirects=False)
                            resp.raise_for_status()
                            total_bytes = 0
                            for chunk in resp.iter_content(chunk_size=8192):
                                total_bytes += len(chunk)
                                if total_bytes > MAX_REMOTE_FILE_BYTES:
                                    raise ValueError('Tài liệu vượt quá dung lượng cho phép.')
                                tmp_file.write(chunk)
                            tmp_file_path = tmp_file.name
                        mime_type, _ = mimetypes.guess_type(target_file_name)
                        if not mime_type:
                            mime_type = 'application/octet-stream'

                    if tmp_file_path:
                        questions_data, images_map = AIGeneratorService.extract_from_file(
                            file_path=tmp_file_path,
                            mime_type=mime_type,
                            subject_name=subject_name
                        )
                        all_questions.extend(questions_data)
                        all_images_map.update(images_map)

                finally:
                    if tmp_file_path and os.path.exists(tmp_file_path):
                        try:
                            os.remove(tmp_file_path)
                        except Exception:
                            pass
            # DEDUPLICATION LOGIC: Remove duplicate extracted questions
            unique_questions = []
            seen_hashes = set()
            for q in all_questions:
                # Build a signature for the question to catch duplicates
                content_json = q.get('content_json', [])
                
                text_parts = [(q.get('text') or '').strip()]
                text_parts.extend([str(b.get('value', '')) for b in content_json if isinstance(b, dict) and b.get('type') == 'text'])
                text_parts.extend([str(b.get('sha256', '')) for b in content_json if isinstance(b, dict) and b.get('type') == 'image'])
                
                if q.get('image'):
                    text_parts.append(str(q.get('image')))
                
                options = q.get('options', [])
                for opt in options:
                    opt_content = opt.get('content_json', [])
                    text_parts.append((opt.get('text') or '').strip())
                    text_parts.extend([str(b.get('value', '')) for b in opt_content if isinstance(b, dict) and b.get('type') == 'text'])
                    text_parts.extend([str(b.get('sha256', '')) for b in opt_content if isinstance(b, dict) and b.get('type') == 'image'])
                    text_parts.append(str(opt.get('is_correct', False)))
                
                if q.get('correct_answer_text'):
                    text_parts.append(str(q.get('correct_answer_text')).strip())
                    
                raw_sig = "||".join(text_parts)
                normalized_sig = re.sub(r'\s+', ' ', raw_sig).strip().lower()
                sig_hash = hashlib.md5(normalized_sig.encode('utf-8')).hexdigest()
                
                if sig_hash not in seen_hashes:
                    seen_hashes.add(sig_hash)
                    unique_questions.append(q)

            return Response({"questions": unique_questions, "images": all_images_map})
        except Exception as e:
            logger.exception('AI file extraction failed')
            for public_id, resource_type in uploaded_assets:
                delete_from_cloudinary(public_id, resource_type=resource_type)
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                msg = "AI hiện đang bận hoặc hết hạn mức (Quota exceeded)."
            else:
                msg = "Không thể trích xuất câu hỏi từ tệp. Vui lòng thử lại sau."
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AIGenerateFromRAGView(APIView):
    """Sinh câu hỏi từ tri thức nội bộ (RAG) của lớp học."""
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def post(self, request):
        class_id = request.data.get('class_id')
        topic = str(request.data.get('topic') or '').strip()[:500]
        try:
            count = int(request.data.get('count', 5))
        except (TypeError, ValueError):
            return Response({"error": "Số lượng câu hỏi không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        count = max(1, min(count, 50))
        question_types = request.data.get('question_types', 'multiple_choice')
        if question_types not in ('multiple_choice', 'true_false', 'short_answer', 'mixed'):
            question_types = 'multiple_choice'
        document_id = request.data.get('document_id')  # Tuỳ chọn: Lọc theo 1 tài liệu cụ thể

        if not class_id:
            return Response({"error": "Thiếu class_id."}, status=status.HTTP_400_BAD_REQUEST)
        if document_id:
            try:
                document_id = int(document_id)
            except (TypeError, ValueError):
                return Response({"error": "document_id không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        _get_class_for_user(request.user, class_id)

        try:
            questions_data = AIGeneratorService.generate_from_rag(
                topic=topic,
                count=count,
                class_id=class_id,
                question_types=question_types,
                document_id=document_id,
            )
            if not questions_data:
                raise NoQuestionsGenerated('AI chưa tạo được câu hỏi. Hãy kiểm tra yêu cầu cần đạt và tài liệu bài học được chọn.')
            return Response({"questions": questions_data})

        except NoQuestionsGenerated as e:
            return Response({"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            logger.exception('AI RAG generation failed')
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                msg = "Hệ thống AI đạt giới hạn (429). Hãy đợi một lát hoặc giảm số lượng câu hỏi cần sinh."
            elif isinstance(e, ValueError):
                msg = "Phản hồi AI không hợp lệ hoặc bị cắt. Vui lòng thử lại với ít câu hỏi hơn."
            else:
                msg = "Không thể sinh câu hỏi. Vui lòng thử lại sau."
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AIBulkSaveQuestionsView(APIView):
    """
    Nhận danh sách câu hỏi (đã review) từ client, lưu vào DB.
    Hỗ trợ cả 3 dạng question_type. Optionally chèn vào Quiz.
    Xử lý việc liên kết khối Image (qua SHA-256) vào QuestionImage.
    """
    permission_classes = [IsAuthenticated, IsTeacherOrAdmin]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def post(self, request):
        questions_data = request.data.get('questions', [])
        quiz_id = request.data.get('quiz_id')
        subject_id = request.data.get('subject_id')

        if not questions_data or not subject_id:
            return Response(
                {"error": "Missing questions or subject_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(questions_data, list):
            return Response({"error": "Danh sách câu hỏi không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        if len(questions_data) > 200:
            return Response({"error": "Số lượng câu hỏi vượt quá giới hạn."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from classes.models import Subject
            from exams.models import ImageBank, QuestionImage
            try:
                subject = Subject.objects.get(id=subject_id)
            except (Subject.DoesNotExist, ValueError, TypeError, DjangoValidationError):
                return Response({"error": "Môn học không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
            quiz = None
            if quiz_id:
                try:
                    quiz = _get_owned_quiz(request.user, quiz_id)
                except (ValueError, TypeError, Http404, PermissionDenied):
                    return Response({"error": "Đề thi không tồn tại hoặc bạn không có quyền."}, status=status.HTTP_403_FORBIDDEN)

            saved_questions = []
            rejected_questions = []

            for index, q_data in enumerate(questions_data):
                if not isinstance(q_data, dict):
                    rejected_questions.append({'index': index, 'reason': 'invalid_question'})
                    continue
                q_type = q_data.get('question_type', 'multiple_choice')
                if q_type not in ('multiple_choice', 'true_false', 'short_answer'):
                    q_type = 'multiple_choice'
                difficulty = q_data.get('difficulty', 'medium')
                if difficulty not in ('easy', 'medium', 'hard'):
                    difficulty = 'medium'
                content_json = q_data.get('content_json', [])
                if not isinstance(content_json, list):
                    content_json = []

                normalized_text = str(q_data.get('text') or '').strip()
                if not normalized_text:
                    normalized_text = self._blocks_to_text(content_json)

                if not normalized_text and not self._has_image_block(content_json):
                    rejected_questions.append({
                        'index': index,
                        'reason': 'missing_question_content',
                    })
                    continue

                image_value = q_data.get('image') or ''
                if not isinstance(image_value, str):
                    image_value = ''

                # 1. Tạo Question
                question = Question.objects.create(
                    question_type=q_type,
                    text=normalized_text,
                    question_text=str(q_data.get('question_text') or '')[:500],
                    topic=str(q_data.get('topic') or '')[:200],
                    content_json=content_json,
                    image=image_value,
                    context=str(q_data.get('context') or ''),
                    correct_answer_text=str(q_data.get('correct_answer_text') or ''),
                    explanation=str(q_data.get('explanation') or ''),
                    subject=subject,
                    difficulty=difficulty,
                    created_by=request.user,
                )

                # 1.1 Quét ImageBlock trong Question.stem
                self._link_images(question, content_json, placement='stem', uploaded_by=request.user)

                # 2. Tạo Options (cho multiple_choice và true_false)
                if q_type in ('multiple_choice', 'true_false'):
                    raw_options = q_data.get('options', [])
                    if not isinstance(raw_options, list):
                        raw_options = []
                    for opt_idx, opt in enumerate(raw_options):
                        if not isinstance(opt, dict):
                            continue
                        opt_content = opt.get('content_json', [])
                        if not isinstance(opt_content, list):
                            opt_content = []
                        opt_text = str(opt.get('text') or '').strip()
                        if not opt_text:
                            opt_text = self._blocks_to_text(opt_content)

                        Option.objects.create(
                            question=question,
                            text=opt_text,
                            content_json=opt_content,
                            is_correct=bool(opt.get('is_correct', False)),
                        )
                        # Quét ImageBlock trong từng phương án
                        self._link_images(question, opt_content, placement=f'choice_{opt_idx}', uploaded_by=request.user)

                # 3. Chèn vào Quiz nếu có
                if quiz:
                    max_order = QuizQuestion.objects.filter(quiz=quiz).count()
                    QuizQuestion.objects.create(
                        quiz=quiz,
                        question=question,
                        order=max_order + 1,
                        points=0.0,
                    )

                    quiz_questions = list(
                        QuizQuestion.objects.filter(quiz=quiz).order_by('order')
                    )
                    total_questions = len(quiz_questions)
                    if total_questions > 0:
                        points_per_question = round(10.0 / total_questions, 2)
                        for qq in quiz_questions:
                            qq.points = points_per_question
                        QuizQuestion.objects.bulk_update(quiz_questions, ['points'])

                saved_questions.append(question.id)

            return Response({
                "detail": f"Đã lưu thành công {len(saved_questions)} câu hỏi.",
                "saved_ids": saved_questions,
                "rejected": rejected_questions,
            })

        except Exception as e:
            logger.exception('AI bulk save failed')
            created_ids = locals().get('saved_questions', [])
            if created_ids:
                try:
                    Question.objects.filter(id__in=created_ids).delete()
                    if locals().get('quiz'):
                        rebalance_quiz_question_points(quiz)
                except Exception:
                    logger.exception('Failed to roll back partially saved questions')
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                msg = "Có lỗi xảy ra khi gọi AI. Vui lòng kiểm tra lại kết nối hoặc hạn mức API."
            else:
                msg = "Không thể lưu câu hỏi. Vui lòng thử lại sau."
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _link_images(self, question, content_json, placement, uploaded_by=None):
        """Duyệt JSON blocks, nếu có type=image, link vào QuestionImage."""
        from exams.models import ImageBank, QuestionImage
        
        if not isinstance(content_json, list):
            return

        pos = 0
        for block in content_json:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'image':
                sha256_hash = block.get('sha256')
                if not isinstance(sha256_hash, str) or not re.fullmatch(r'[a-fA-F0-9]{32,64}', sha256_hash):
                    sha256_hash = None
                direct_url = block.get('url')
                if not isinstance(direct_url, str):
                    direct_url = None
                
                if sha256_hash:
                    try:
                        img_bank = ImageBank.objects.get(sha256=sha256_hash)
                        QuestionImage.objects.get_or_create(
                            question=question,
                            image=img_bank,
                            position=pos,
                            placement=placement,
                            defaults={
                                'source_type': 'ai_scan',
                                'uploaded_by': uploaded_by,
                            },
                        )
                        pos += 1
                    except ImageBank.DoesNotExist:
                        # Fallback: Nếu không có ImageBank nhưng có URL trong block
                        if direct_url:
                            QuestionImage.objects.create(
                                question=question,
                                image_url=direct_url,
                                position=pos,
                                placement=placement,
                                source_type='ai_scan',
                                uploaded_by=uploaded_by
                            )
                            pos += 1
                elif direct_url:
                    # Trường hợp chỉ có URL (vd: AI sinh từ RAG hoặc URL trực tiếp)
                    QuestionImage.objects.create(
                        question=question,
                        image_url=direct_url,
                        position=pos,
                        placement=placement,
                        source_type='ai_scan',
                        uploaded_by=uploaded_by
                    )
                    pos += 1

    def _blocks_to_text(self, blocks):
        if not isinstance(blocks, list):
            return ''
        parts = []
        for b in blocks:
            if isinstance(b, dict):
                if b.get('type') == 'text' and isinstance(b.get('value'), str):
                    parts.append(b.get('value'))
                elif b.get('type') == 'image' and b.get('sha256'):
                    parts.append(f"\n[IMAGE_PLACEHOLDER:{b.get('sha256')}]\n")
        return ' '.join(parts).strip()

    def _has_image_block(self, blocks):
        if not isinstance(blocks, list):
            return False
        return any(isinstance(b, dict) and b.get('type') == 'image' for b in blocks)

# ─── MẢNG 3: AI CÁ NHÂN HÓA ─────────────────────────────────────────────────

class AIPersonalizedPathView(APIView):
    """Đề xuất lộ trình học tập cá nhân hóa dựa trên kết quả các bài quiz."""
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def get(self, request):
        user = request.user
        
        from exams.models import QuizAttempt, StudentAnswer
        attempts = QuizAttempt.objects.filter(student=user, is_completed=True).select_related('quiz')
        
        if not attempts.exists():
            return Response({"insight": "Bạn chưa hoàn thành bài thi nào để AI có thể phân tích lộ trình học tập. Hãy hoàn thành ít nhất 1 bài thi."})
            
        subject_stats = {}
        wrong_questions_by_subject = {}
        
        answers = StudentAnswer.objects.filter(attempt__in=attempts).select_related('quiz_question__question', 'quiz_question__question__subject').order_by('id')
        for ans in answers:
            q = ans.quiz_question.question
            subj = q.subject.name if q.subject else "Chung"
            is_corr = ans.is_correct()
            
            if subj not in subject_stats:
                subject_stats[subj] = {'total': 0, 'correct': 0}
            subject_stats[subj]['total'] += 1
            if is_corr:
                subject_stats[subj]['correct'] += 1
            else:
                if subj not in wrong_questions_by_subject:
                    wrong_questions_by_subject[subj] = []
                q_text = str(q.text or '').strip()
                if q.context:
                    q_text = f"{q.context[:50]}... {q_text}"
                q_text_short = q_text[:100] + '...' if len(q_text) > 100 else q_text
                if q_text_short and q_text_short not in wrong_questions_by_subject[subj]:
                    wrong_questions_by_subject[subj].append(q_text_short)
                
        # Giới hạn số lượng câu sai hiển thị cho AI để tránh quá tải token (5 câu mới nhất mỗi môn)
        for subj in wrong_questions_by_subject:
            wrong_questions_by_subject[subj] = wrong_questions_by_subject[subj][-5:]
                
        # Lấy thông tin lớp học của học sinh để AI hiểu rõ ngữ cảnh cấp học
        class_context = ""
        try:
            from classes.models import ClassStudent
            enrolled = ClassStudent.objects.filter(student=user).select_related('classroom')
            class_names = [e.classroom.name for e in enrolled if e.classroom]
            if class_names:
                class_context = f"\nThông tin đối tượng: Học sinh đang học tại các lớp [{', '.join(class_names)}]. Hãy điều chỉnh phương pháp học, thuật ngữ và lời khuyên sao cho bám sát chương trình và trình độ của học sinh lớp này."
        except Exception:
            pass

        prompt = f"""
Bạn là một gia sư AI tận tâm. Dựa trên dữ liệu dưới đây, hãy đề xuất một lộ trình học tập cá nhân hóa nhằm khắc phục các lỗ hổng kiến thức.{class_context}

DỮ LIỆU TỔNG QUAN (Số câu đúng / Tổng số câu):
{json.dumps(subject_stats, ensure_ascii=False)}

CÁC CÂU HỎI HỌC SINH ĐÃ LÀM SAI GẦN ĐÂY (Nội dung tóm tắt):
{json.dumps(wrong_questions_by_subject, ensure_ascii=False, indent=2)}

YÊU CẦU LỘ TRÌNH ĐỀ XUẤT:
1. Đưa ra nhận xét ngắn gọn, khích lệ người học.
2. PHÂN TÍCH LỖ HỔNG: Phân tích cụ thể nội dung các câu hỏi mà học sinh làm sai ở trên. ĐƯỢC PHÉP DÙNG KIẾN THỨC BÊN NGOÀI (Open Knowledge) để suy luận xem học sinh đang bị yếu ở những dạng bài tập nào, hoặc quên mất khái niệm lý thuyết cụ thể nào.
3. ĐỀ XUẤT LỘ TRÌNH ÔN TẬP: Ghi rõ tên các bài học, định lý, công thức, hoặc mảng kiến thức cụ thể cần ôn lại dựa trên sự phân tích trên. Không nói chung chung kiểu "hãy ôn lại môn Toán", mà phải nói cụ thể "hãy ôn lại cách tính đạo hàm hàm hợp, hay ngữ pháp câu điều kiện loại 2...".
4. TRÌNH BÀY BẰNG MARKDOWN: Sử dụng CÁC THẺ HEADING (#, ##) và BẮT BUỘC PHẢI XUỐNG DÒNG (line break) rõ ràng giữa các đoạn văn, các heading và các mục danh sách để dễ đọc.

QUAN TRỌNG - CẤM TUYỆT ĐỐI:
- KHÔNG được thêm mục "Tài liệu tham khảo", "Sách tham khảo", "Nguồn tài liệu" hay bất kỳ danh sách sách/tài liệu cụ thể nào.
- Học sinh có thể tự tìm tài liệu từ nhiều nguồn khác nhau. Chỉ tập trung vào nội dung kiến thức và kỹ năng cần ôn luyện.
"""
        try:
            response = ai_client.generate_content(prompt)
            return Response({"insight": response.text})
        except Exception:
            return Response({"error": "Lỗi kết nối AI."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AIGenerateQuickTestView(APIView):
    """Tạo nhanh 1 bài quiz ngẫu nhiên tập trung vào điểm yếu."""
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'

    def post(self, request):
        user = request.user
        try:
            from exams.models import Question, Quiz, QuizQuestion
            import random
            from django.utils import timezone
            
            # Logic: Collect questions the student got wrong recently
            from exams.models import StudentAnswer
            wrong_answers = StudentAnswer.objects.filter(attempt__student=user, attempt__is_completed=True).order_by('-id')[:50]
            wrong_questions = [ans.quiz_question.question for ans in wrong_answers if not ans.is_correct()]

            target_class = None
            from classes.models import ClassStudent
            if wrong_answers.exists():
                target_class = wrong_answers[0].attempt.quiz.classroom

            if target_class and not ClassStudent.objects.filter(
                classroom=target_class, student=user
            ).exists():
                target_class = None

            if not target_class:
                cs = ClassStudent.objects.filter(student=user).first()
                if cs:
                    target_class = cs.classroom

            if not target_class:
                return Response({"error": "Bạn cần tham gia ít nhất 1 lớp học để tạo bài ôn tập."}, status=status.HTTP_400_BAD_REQUEST)

            pool = list(set(wrong_questions))
            if len(pool) < 5:
                # Not enough wrong questions, pad with questions from the same subject
                pool.extend(list(Question.objects.filter(subject=target_class.subject).order_by('?')[:10]))
                pool = list(set(pool))
                
            if not pool:
                return Response({"error": "Không có đủ câu hỏi trong ngân hàng để tạo Quick Test."}, status=status.HTTP_400_BAD_REQUEST)
                
            selected = random.sample(pool, min(10, len(pool)))
            
            quiz = Quiz.objects.create(
                title=f"Phục thù - Luyện tập thần tốc ngày {timezone.now().strftime('%d/%m')}",
                description="Bài kiểm tra tự động tạo ra từ phân tích điểm yếu của bạn, tập trung vào các câu bạn đã làm sai.",
                duration_minutes=len(selected) * 2,
                classroom=target_class,
                created_by=user,
                assigned_to=user,
                is_published=True
            )
            
            for idx, q in enumerate(selected):
                QuizQuestion.objects.create(
                    quiz=quiz,
                    question=q,
                    order=idx + 1,
                    points=round(10.0 / len(selected), 2)
                )
                
            return Response({"quiz_id": quiz.id, "message": "Quick Test đã sẵn sàng!"})
            
        except Exception:
            logger.exception('Quick test generation failed')
            return Response({"error": "Không thể tạo bài ôn tập. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AIExplainWrongAnswerView(APIView):
    """API cho phép học sinh gọi AI để giải thích câu hỏi làm sai trên kết quả bài thi."""
    permission_classes = [IsAuthenticated]
    throttle_classes = AI_THROTTLE_CLASSES
    throttle_scope = 'ai_generate'
    
    def post(self, request):
        if getattr(request.user.role, 'name', None) not in ['student', 'teacher', 'admin'] and not request.user.is_superuser:
            return Response({"error": "Bạn không có quyền thực hiện chức năng này."}, status=status.HTTP_403_FORBIDDEN)
            
        question_text = request.data.get('question_text')
        correct_answer = request.data.get('correct_answer')
        student_answer = request.data.get('student_answer')
        
        if not all([question_text, correct_answer, student_answer]):
            return Response({"error": "Vui lòng cung cấp đầy đủ thông tin câu hỏi, đáp án đúng và đáp án đã chọn."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            explanation = AIGeneratorService.explain_wrong_answer(
                question_text=str(question_text)[:2000],
                correct_answer=str(correct_answer)[:500],
                student_answer=str(student_answer)[:500]
            )
            return Response({"explanation": explanation})
        except Exception:
            logger.exception('AI explanation failed')
            return Response({"error": "Lỗi AI. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

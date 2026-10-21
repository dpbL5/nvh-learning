from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User, Role
from .serializers import (
    ChangePasswordSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .authentication import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)


def _is_teacher_or_admin(user):
    role = getattr(user.role, 'name', None)
    return role in ['teacher', 'admin'] or user.is_superuser


def _is_admin(user):
    return getattr(user.role, 'name', None) == 'admin' or user.is_superuser


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh') or request.COOKIES.get(REFRESH_COOKIE)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                pass
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        return clear_auth_cookies(response)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = False
        self.fields['email'] = serializers.EmailField(required=False, write_only=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token

    def validate(self, attrs):
        login_value = attrs.get('username') or attrs.get('email')
        if not login_value:
            raise serializers.ValidationError('Vui long nhap username hoac email.')
        attrs['username'] = login_value
        return super().validate(attrs)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            set_auth_cookies(
                response,
                access=response.data.get('access'),
                refresh=response.data.get('refresh'),
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get('refresh'):
            data['refresh'] = request.COOKIES.get(REFRESH_COOKIE)
        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        access = serializer.validated_data.get('access')
        refresh = serializer.validated_data.get('refresh')
        response = Response({'detail': 'ok'})
        return set_auth_cookies(response, access=access, refresh=refresh)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])
        return Response({'detail': 'Đổi mật khẩu thành công.'})


class UserListView(generics.ListAPIView):
    """Admin-only: list all users in the system."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not _is_admin(self.request.user):
            return User.objects.none()
        return User.objects.all().select_related('role').order_by('created_at')

    def list(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({'detail': 'Chỉ admin mới có thể xem danh sách người dùng.'}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Admin-only: get or update a specific user (e.g. change role)."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.all().select_related('role')

    def get_object(self):
        if not _is_admin(self.request.user):
            self.permission_denied(self.request, message='Chỉ admin mới có quyền này.')
        return super().get_object()

    def update(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            return Response({'detail': 'Không có quyền.'}, status=status.HTTP_403_FORBIDDEN)
        # Allow changing role by name
        role_name = request.data.get('role_name')
        if role_name:
            role_name = str(role_name).strip().lower()
            if role_name not in (Role.STUDENT, Role.TEACHER, Role.ADMIN):
                return Response({'detail': f'Role "{role_name}" không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                role, _ = Role.objects.get_or_create(name=role_name)
                user = self.get_object()
                old_role_name = getattr(user.role, 'name', None)
                user.role = role
                user.save()
                
                # Update profiles based on new role
                import uuid
                if role_name != old_role_name:
                    if role_name == 'teacher':
                        if hasattr(user, 'student_profile'):
                            user.student_profile.delete()
                        if not hasattr(user, 'teacher_profile'):
                            from .models import TeacherProfile
                            code = 'GV-' + uuid.uuid4().hex[:8].upper()
                            TeacherProfile.objects.create(user=user, teacher_code=code)
                    elif role_name == 'student':
                        if hasattr(user, 'teacher_profile'):
                            user.teacher_profile.delete()
                        if not hasattr(user, 'student_profile'):
                            from .models import StudentProfile
                            code = 'HS-' + uuid.uuid4().hex[:8].upper()
                            StudentProfile.objects.create(user=user, student_code=code)
                    elif role_name == 'admin':
                        if hasattr(user, 'student_profile'):
                            user.student_profile.delete()
                        if hasattr(user, 'teacher_profile'):
                            user.teacher_profile.delete()

                return Response(UserSerializer(user).data)
            except Role.DoesNotExist:
                return Response({'detail': f'Role "{role_name}" không tồn tại.'}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)


from django.db.models import Avg, Sum, Count
from classes.models import Class, Subject, ClassStudent
from exams.models import Quiz, QuizAttempt

class DashboardStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user.role, 'name', None)
        
        data = {
            'role': role,
            'stats': {},
            'recent_activities': []
        }

        if role == 'admin' or user.is_superuser:
            data['stats'] = {
                'total_users': User.objects.count(),
                'total_teachers': User.objects.filter(role__name='teacher').count(),
                'total_students': User.objects.filter(role__name='student').count(),
                'total_classes': Class.objects.count(),
                'total_subjects': Subject.objects.count(),
                'total_quizzes': Quiz.objects.exclude(created_by__role__name='student').count(),
                'total_attempts': QuizAttempt.objects.filter(is_completed=True).exclude(quiz__created_by__role__name='student').count(),
                'avg_score_system': round(QuizAttempt.objects.filter(is_completed=True).exclude(quiz__created_by__role__name='student').aggregate(Avg('score'))['score__avg'] or 0, 2),
            }
            # Recent registrations
            recent_users = User.objects.order_by('-created_at')[:5]
            for u in recent_users:
                data['recent_activities'].append({
                    'type': 'new_user',
                    'title': f'Người dùng mới: {u.username}',
                    'time': u.created_at,
                    'detail': f'Email: {u.email}'
                })

        elif role == 'teacher':
            classes = Class.objects.filter(teacher=user)
            data['stats'] = {
                'total_classes': classes.count(),
                'total_students': ClassStudent.objects.filter(classroom__in=classes).values('student').distinct().count(),
                'total_quizzes': Quiz.objects.filter(classroom__in=classes).exclude(created_by__role__name='student').count(),
            }
            # Recent submissions in their classes
            recent_attempts = QuizAttempt.objects.filter(
                quiz__classroom__in=classes,
                is_completed=True,
            ).exclude(quiz__created_by__role__name='student').order_by('-end_time')[:5]
            for a in recent_attempts:
                data['recent_activities'].append({
                    'type': 'quiz_submission',
                    'title': f'{a.student.username} nộp bài {a.quiz.title}',
                    'time': a.end_time,
                    'detail': f'Điểm số: {a.score}/10'
                })

        elif role == 'student':
            attempts = QuizAttempt.objects.filter(student=user, is_completed=True)
            data['stats'] = {
                'joined_classes': ClassStudent.objects.filter(student=user).count(),
                'completed_quizzes': attempts.count(),
                'avg_score': round(attempts.aggregate(Avg('score'))['score__avg'] or 0, 1),
            }
            # Their recent quiz results
            recent_attempts = attempts.order_by('-end_time')[:5]
            for a in recent_attempts:
                data['recent_activities'].append({
                    'type': 'quiz_result',
                    'title': f'Hoàn thành bài: {a.quiz.title}',
                    'time': a.end_time,
                    'detail': f'Bạn đạt được: {a.score}/10'
                })


        return Response(data)


def _build_report_queryset(user, params):
    """Helper to build filtered queryset for reports."""
    from django.utils.dateparse import parse_date

    from_date = params.get('from_date')
    to_date = params.get('to_date')
    teacher_id = params.get('teacher_id')
    class_id = params.get('class_id')

    qs = (
        QuizAttempt.objects
        .filter(is_completed=True)
        .exclude(quiz__created_by__role__name='student')
        .select_related(
            'student', 'student__student_profile',
            'quiz', 'quiz__classroom', 'quiz__classroom__teacher', 'quiz__classroom__subject'
        )
    )

    # Role-based filtering
    role_name = getattr(user.role, 'name', None)
    if role_name == 'teacher':
        # Teachers only see their own classes
        qs = qs.filter(quiz__classroom__teacher=user)
    elif role_name == 'admin' or user.is_superuser:
        # Admins can filter by specific teacher
        if teacher_id:
            qs = qs.filter(quiz__classroom__teacher_id=teacher_id)
    else:
        # Other roles see nothing
        return QuizAttempt.objects.none()

    if from_date:
        parsed_from = parse_date(str(from_date))
        if not parsed_from:
            raise ValueError('from_date không hợp lệ.')
        qs = qs.filter(end_time__date__gte=parsed_from)
    if to_date:
        parsed_to = parse_date(str(to_date))
        if not parsed_to:
            raise ValueError('to_date không hợp lệ.')
        qs = qs.filter(end_time__date__lte=parsed_to)
    if class_id:
        qs = qs.filter(quiz__classroom_id=class_id)

    return qs.order_by('-end_time')


class AdminReportView(APIView):
    """Admin-only: Get a list of quiz attempts with filters."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_teacher_or_admin(request.user):
            return Response({'detail': 'Bạn không có quyền xem báo cáo.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            qs = _build_report_queryset(request.user, request.query_params)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError:
            return Response({'detail': 'Bộ lọc báo cáo không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Simple manual pagination
        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 50))
        except (TypeError, ValueError):
            return Response({'detail': 'Tham số phân trang không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        start = (page - 1) * page_size
        end = start + page_size
        
        count = qs.count()
        results = qs[start:end]

        data = []
        for a in results:
            data.append({
                'student_name': a.student.full_name,
                'student_code': getattr(a.student.student_profile, 'student_code', 'N/A'),
                'class_name': a.quiz.classroom.name,
                'subject': a.quiz.classroom.subject.name,
                'teacher_name': a.quiz.classroom.teacher.full_name,
                'quiz_title': a.quiz.title,
                'score': a.score,
                'completed_at': a.end_time,
            })

        return Response({
            'count': count,
            'page': page,
            'page_size': page_size,
            'results': data
        })


from django.http import HttpResponse
import openpyxl

class AdminExportView(APIView):
    """Admin-only: Export quiz attempts to Excel."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_teacher_or_admin(request.user):
            return Response({'detail': 'Bạn không có quyền xuất dữ liệu.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            qs = _build_report_queryset(request.user, request.query_params)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError:
            return Response({'detail': 'Bộ lọc báo cáo không hợp lệ.'}, status=status.HTTP_400_BAD_REQUEST)

        max_rows = 10000
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title="Bảng điểm")

        # Headers
        headers = ["STT", "Học sinh", "Mã HS", "Lớp", "Môn", "Giáo viên", "Tên đề", "Điểm", "Thời gian nộp"]
        ws.append(headers)

        # Data (capped and streamed to the response)
        for idx, a in enumerate(qs[:max_rows].iterator(), 1):
            ws.append([
                idx,
                a.student.full_name,
                getattr(a.student.student_profile, 'student_code', 'N/A'),
                a.quiz.classroom.name,
                a.quiz.classroom.subject.name,
                a.quiz.classroom.teacher.full_name,
                a.quiz.title,
                a.score,
                a.end_time.strftime("%d/%m/%Y %H:%M") if a.end_time else ""
            ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename=bang_diem.xlsx'
        wb.save(response)
        return response

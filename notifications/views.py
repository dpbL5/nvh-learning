import logging
import os

from django.core.management import call_command
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — danh sách thông báo của người dùng hiện tại."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('actor').order_by('-created_at')


class UnreadCountView(APIView):
    """GET /api/notifications/unread-count/ — số thông báo chưa đọc."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'count': count})


class MarkReadView(APIView):
    """PATCH /api/notifications/<id>/read/ — đánh dấu một thông báo đã đọc."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Không tìm thấy thông báo.'}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data)


class MarkAllReadView(APIView):
    """POST /api/notifications/mark-all-read/ — đánh dấu tất cả thông báo đã đọc."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({'marked_read': updated})


class RunDueNotificationsView(APIView):
    """Cron endpoint: notify students about quizzes whose publish_at time has passed."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        secret = os.getenv('CRON_SECRET', '')
        if not secret or request.headers.get('Authorization') != f'Bearer {secret}':
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        try:
            call_command('notify_due_quizzes')
        except Exception:
            logger.exception('notify_due_quizzes failed')
            return Response({'detail': 'Cron job failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': 'ok'})

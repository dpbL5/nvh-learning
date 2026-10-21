from django.urls import path
from .views import (
    NotificationListView,
    UnreadCountView,
    MarkReadView,
    MarkAllReadView,
    RunDueNotificationsView,
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('run-due/', RunDueNotificationsView.as_view(), name='notification-run-due'),
    path('<int:pk>/read/', MarkReadView.as_view(), name='notification-mark-read'),
    path('mark-all-read/', MarkAllReadView.as_view(), name='notification-mark-all-read'),
]

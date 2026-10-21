from django.urls import path
from .views import (
    RegisterView, MeView, CustomTokenObtainPairView, CookieTokenRefreshView, LogoutView,
    UserListView, UserDetailView, DashboardStatsView, AdminReportView, AdminExportView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    # Admin-only
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('admin/report/', AdminReportView.as_view(), name='admin-report'),
    path('admin/export/', AdminExportView.as_view(), name='admin-export'),
]

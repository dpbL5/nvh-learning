"""
URL configuration for nvh_learning project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from nvh_learning import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/classes/', include('classes.urls')),
    path('api/exams/', include('exams.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/ai/', include('ai_core.urls')),
    # Frontend views
    path('', core_views.home_view, name='home'),
    path('login/', core_views.login_view, name='login'),
    path('register/', core_views.register_view, name='register'),
    path('dashboard/', core_views.dashboard_view, name='dashboard'),
    path('classes/', core_views.classes_view, name='classes'),
    path('classes/<uuid:class_id>/', core_views.class_detail_view, name='class-detail'),
    path('exams/builder/<int:quiz_id>/', core_views.quiz_builder_view, name='quiz-builder'),
    path('exams/taker/<int:quiz_id>/', core_views.quiz_taker_view, name='quiz-taker'),
    path('exams/question-bank/', core_views.question_bank_view, name='question-bank'),
    path('admin-panel/', core_views.admin_panel_view, name='admin-panel'),
    path('logout/', core_views.logout_view, name='logout'),
    path('notifications/', core_views.notifications_view, name='notifications'),
    path('profile/', core_views.profile_view, name='profile'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

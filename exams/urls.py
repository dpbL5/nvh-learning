from django.urls import path
from .views import (
    QuestionListCreateView, QuestionDetailView, OptionListCreateView,
    QuizListCreateView, QuizDetailView, QuizQuestionListCreateView,
    QuizQuestionDetailView, UploadImageView,
    CloudinarySignatureView,
    QuestionImageUploadView, QuestionImageLinkView, QuestionImageUnlinkView,
    StudentQuizListView, QuizStartView, QuizSubmitView, ClassAnalyticsView,
    BulkDeleteQuestionsView, StudentProgressAPIView, TeacherAdminProgressAPIView
)

urlpatterns = [
    # Teacher/Admin: Question Bank CRUD
    path('questions/', QuestionListCreateView.as_view(), name='question-list-create'),
    path('questions/bulk-delete/', BulkDeleteQuestionsView.as_view(), name='question-bulk-delete'),
    path('questions/<int:pk>/', QuestionDetailView.as_view(), name='question-detail'),
    path('questions/<int:pk>/update-full/', QuestionDetailView.as_view(), name='question-update-full'),
    path('questions/images/upload/', QuestionImageUploadView.as_view(), name='question-image-upload'),
    path('cloudinary-signature/', CloudinarySignatureView.as_view(), name='cloudinary-signature'),
    path('questions/<int:pk>/images/link/', QuestionImageLinkView.as_view(), name='question-image-link'),
    path('questions/<int:pk>/images/<int:qimg_id>/', QuestionImageUnlinkView.as_view(), name='question-image-unlink'),
    path('questions/<int:question_id>/options/', OptionListCreateView.as_view(), name='option-list-create'),
    path('upload-image/', UploadImageView.as_view(), name='upload-image'),

    # Teacher/Admin: Quizzes CRUD
    path('', QuizListCreateView.as_view(), name='quiz-list-create'),
    path('<int:pk>/', QuizDetailView.as_view(), name='quiz-detail'),
    path('analytics/<uuid:class_id>/', ClassAnalyticsView.as_view(), name='class-analytics'),
    path('<int:quiz_id>/questions/', QuizQuestionListCreateView.as_view(), name='quiz-question-list-create'),
    path('<int:quiz_id>/questions/<int:pk>/', QuizQuestionDetailView.as_view(), name='quiz-question-detail'),
    path('teacher-progress/', TeacherAdminProgressAPIView.as_view(), name='teacher-progress'),
    path('student-progress/', StudentProgressAPIView.as_view(), name='student-progress'),


    # Student: Take Exams
    path('my-quizzes/', StudentQuizListView.as_view(), name='student-quizzes'),
    path('<int:quiz_id>/start/', QuizStartView.as_view(), name='quiz-start'),
    path('attempt/<int:attempt_id>/submit/', QuizSubmitView.as_view(), name='quiz-submit'),

]

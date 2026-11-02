from django.urls import path
from .views import (
    RAGChatbotView, AIClassInsightView,
    ClassDocumentListView, UploadClassDocumentView, DocumentDetailView,
    DocumentCopyView,
    AIExtractFromFileView, AIGenerateFromRAGView, AIBulkSaveQuestionsView,
    AIPersonalizedPathView, AIGenerateQuickTestView,
    AIExplainWrongAnswerView
)

urlpatterns = [
    path('chat/', RAGChatbotView.as_view(), name='rag-chatbot'),
    path('insight/', AIClassInsightView.as_view(), name='ai-insight'),
    path('classes/<uuid:class_id>/documents/', ClassDocumentListView.as_view(), name='class-docs'),
    path('classes/<uuid:class_id>/documents/upload/', UploadClassDocumentView.as_view(), name='upload-class-doc'),
    path('documents/<int:doc_id>/', DocumentDetailView.as_view(), name='class-doc-detail'),
    path('documents/<int:doc_id>/copy/', DocumentCopyView.as_view(), name='copy-class-doc'),
    # AI Generation tools for Question Bank
    path('generate/extract-file/', AIExtractFromFileView.as_view(), name='ai-extract-file'),
    path('generate/from-rag/', AIGenerateFromRAGView.as_view(), name='ai-generate-rag'),
    path('generate/save-bulk/', AIBulkSaveQuestionsView.as_view(), name='ai-save-bulk'),
    
    # Path & Quick Test AI 
    path('path/', AIPersonalizedPathView.as_view(), name='ai-personalized-path'),
    path('quick-test/', AIGenerateQuickTestView.as_view(), name='ai-quick-test'),
    
    # Explain wrong answer
    path('explain-wrong-answer/', AIExplainWrongAnswerView.as_view(), name='ai-explain-wrong-answer'),
]

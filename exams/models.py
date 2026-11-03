from django.db import models
from accounts.models import User
from classes.models import Class, Subject

from .scoring import is_answer_correct


class ImageBank(models.Model):
    """
    Lưu trữ hình ảnh (PNG) sinh ra từ DOCX/WMF.
    Content-addressed storage: dùng SHA-256 làm Primary Key.
    """
    sha256 = models.CharField(max_length=64, primary_key=True)
    image_file = models.ImageField(upload_to='questions/images/bank/')
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="Dung lượng ảnh theo bytes")
    width_pt = models.FloatField(null=True, blank=True, help_text="Độ rộng hiển thị (pt) trong docx gốc")
    height_pt = models.FloatField(null=True, blank=True, help_text="Độ cao hiển thị (pt) trong docx gốc")
    image_url = models.URLField(max_length=1000, blank=True, null=True, help_text="Link ảnh trực tiếp (vd: Cloudinary)")
    cloudinary_public_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image_{self.sha256[:8]}"


class Question(models.Model):
    """
    Câu hỏi ngân hàng — hỗ trợ 3 dạng theo format đề thi THPT 2025:
      - multiple_choice: Trắc nghiệm chọn 1/4 (A/B/C/D)
      - true_false: Đúng/Sai — 1 ngữ cảnh kèm 4 phát biểu xét Đúng/Sai riêng biệt
      - short_answer: Trả lời ngắn — điền kết quả (số/text), không có gợi ý
    """
    QUESTION_TYPE_CHOICES = (
        ('multiple_choice', 'Trắc nghiệm (chọn 1/4)'),
        ('true_false', 'Đúng / Sai'),
        ('short_answer', 'Trả lời ngắn'),
    )
    DIFFICULTY_CHOICES = (
        ('easy', 'Nhận biết'),
        ('medium', 'Thông hiểu'),
        ('hard', 'Vận dụng'),
    )
    GRADE_CHOICES = (
        ('10', 'Lớp 10'),
        ('11', 'Lớp 11'),
        ('12', 'Lớp 12'),
    )

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='multiple_choice',
        help_text="Dạng câu hỏi theo format đề thi THPT 2025."
    )
    text = models.TextField(help_text="Nội dung câu hỏi chính (text thô).", blank=True, null=True)
    question_text = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Tiêu đề/vấn đề chính (dùng cho dạng Đúng/Sai)."
    )
    topic = models.CharField(max_length=200, blank=True, default='', help_text="Chủ đề cụ thể.")
    content_json = models.JSONField(
        blank=True, null=True, 
        help_text="Nội dung câu hỏi dạng blocks [{type: 'text', value: '...'}, {type: 'image', sha256: '...'}]"
    )
    context = models.TextField(
        blank=True, null=True,
        help_text="Ngữ cảnh/đoạn dẫn (dùng cho dạng Đúng/Sai hoặc câu hỏi có bối cảnh)."
    )
    image = models.ImageField(upload_to='questions/images/', null=True, blank=True, help_text="Hình ảnh đính kèm cũ (nếu có).")
    correct_answer_text = models.CharField(
        max_length=500, blank=True, null=True,
        help_text="Đáp án đúng dạng text (dùng cho dạng Trả lời ngắn)."
    )
    explanation = models.TextField(
        blank=True, null=True,
        help_text="Lời giải thích chi tiết cho toàn bộ câu hỏi."
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    grade = models.CharField(
        max_length=2, choices=GRADE_CHOICES, blank=True, default='', db_index=True,
        help_text="Khối lớp (10/11/12). Để trống nếu chưa phân loại.",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_questions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Fallback to text if available, otherwise just question type
        display_text = (self.text or "")[:50]
        return f"[{self.get_question_type_display()}] {self.subject.name} - {display_text}"


class QuestionImage(models.Model):
    """
    Liên kết 1 câu hỏi với N ảnh trong ImageBank.
    """
    SOURCE_TYPE_CHOICES = (
        ('ai_scan', 'AI Scan'),
        ('user_upload', 'User Upload'),
        ('system', 'System'),
    )

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='question_images')
    image = models.ForeignKey(ImageBank, on_delete=models.CASCADE, null=True, blank=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True, help_text="Link ảnh trực tiếp từ AI/Cloudinary")
    position = models.IntegerField(default=0, help_text="Thứ tự xuất hiện")
    placement = models.CharField(max_length=50, default='stem', help_text="Vị trí: stem, choice_A, sub_a...")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='user_upload')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='question_images_uploaded')
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']
        # Remove unique_together as it might conflict with null image and we want flexibility
        # unique_together = ('question', 'image', 'placement', 'position')
        
    def __str__(self):
        image_label = self.image.sha256[:8] if self.image else (self.image_url or 'no-image')
        return f"Q{self.question_id} -> {image_label}"


class Option(models.Model):
    """
    Phương án cho câu hỏi.
    - multiple_choice: 4 option, 1 is_correct=True
    - true_false: 4 phát biểu, mỗi cái is_correct = Đúng hoặc Sai
    - short_answer: Không dùng Option (dùng correct_answer_text trên Question)
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500, blank=True, null=True)
    content_json = models.JSONField(
        blank=True, null=True, 
        help_text="Nội dung phương án dạng blocks (tương tự câu hỏi)"
    )
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(
        blank=True, null=True,
        help_text="Lời giải thích chi tiết cho phương án này."
    )

    def __str__(self):
        return f"{self.text} ({'Đúng' if self.is_correct else 'Sai'})"


class Quiz(models.Model):
    """A quiz/exam assigned to a specific class."""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    classroom = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='quizzes')
    duration_minutes = models.IntegerField(default=45, help_text="Thời gian làm bài (phút)")
    is_published = models.BooleanField(default=False, help_text="Học sinh có thể thấy bài này chưa?")
    publish_at = models.DateTimeField(null=True, blank=True, help_text="Hẹn giờ công khai")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='assigned_quizzes', help_text="Nếu có, bài này chỉ dành riêng cho học sinh này (VD: bài Phục thù).")
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.classroom.name}"


class QuizQuestion(models.Model):
    """Mapping a question into a quiz (allows reuse of bank)."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='quiz_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    points = models.FloatField(default=1.0)
    is_points_overridden = models.BooleanField(
        default=False,
        help_text="Giáo viên đã tự sửa điểm câu này; không tự động tính lại.",
    )

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'question'], name='uniq_quiz_question'),
        ]

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"


class QuizAttempt(models.Model):
    """A single attempt of a student taking a quiz."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['quiz', 'student'],
                name='uniq_quiz_attempt',
            ),
        ]

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} ({self.score})"


class StudentAnswer(models.Model):
    """
    Câu trả lời của học sinh — hỗ trợ cả 3 dạng:
      - multiple_choice: selected_option (FK -> Option)
      - true_false: selected_option (FK -> Option) + answer_value (bool Đúng/Sai)
      - short_answer: answer_text (điền đáp án)
    """
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    quiz_question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.SET_NULL, null=True, blank=True)
    answer_text = models.CharField(
        max_length=500, blank=True, null=True,
        help_text="Đáp án text (cho dạng trả lời ngắn)."
    )
    answer_value = models.BooleanField(
        null=True, blank=True,
        help_text="Học sinh chọn Đúng (True) / Sai (False) cho từng phát biểu ở dạng Đúng/Sai.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'quiz_question', 'selected_option'],
                condition=models.Q(selected_option__isnull=False),
                name='uniq_student_answer_option',
            ),
            models.UniqueConstraint(
                fields=['attempt', 'quiz_question'],
                condition=models.Q(selected_option__isnull=True),
                name='uniq_student_answer_text',
            ),
        ]

    def is_correct(self):
        """Kiểm tra đáp án đúng dựa trên dạng câu hỏi."""
        return is_answer_correct(
            self.quiz_question.question,
            selected_option=self.selected_option,
            answer_text=self.answer_text,
            answer_value=self.answer_value,
        )

    def __str__(self):
        return f"{self.attempt.student.username} -> {self.selected_option or self.answer_text}"

from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Thông báo trong ứng dụng.
    - recipient : người nhận thông báo
    - actor     : người kích hoạt (giáo viên, có thể null)
    - verb      : mã hành động, vd 'published_quiz'
    - message   : nội dung người dùng đọc được (tiếng Việt)
    - target_id : pk của đối tượng liên quan (vd quiz.id)
    - is_read   : đã đọc chưa
    """
    VERB_PUBLISHED_QUIZ = 'published_quiz'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_notifications',
    )
    verb = models.CharField(max_length=50, default=VERB_PUBLISHED_QUIZ)
    message = models.CharField(max_length=500)
    target_id = models.IntegerField(null=True, blank=True, help_text="PK của Quiz liên quan")
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'verb', 'target_id'],
                name='uniq_notification_recipient_target',
            ),
        ]

    def __str__(self):
        return f"[{self.verb}] → {self.recipient.username}: {self.message[:60]}"

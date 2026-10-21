import uuid
import secrets
import string
from django.db import models
from django.conf import settings


def generate_invite_code():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'subjects'

    def __str__(self):
        return self.name





class Class(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='classes')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='taught_classes'
    )
    invite_code = models.CharField(max_length=8, unique=True, default=generate_invite_code, editable=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'classes'

    def __str__(self):
        return f'{self.name} ({self.subject})'


class ClassStudent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_students')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrolled_classes'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_students'
        unique_together = ('classroom', 'student')

    def __str__(self):
        return f'{self.student} → {self.classroom}'

"""
Signals for in-app notifications.
- Quiz published: notify enrolled students when it is actually visible.
- Student joins a class: notify them about already-visible published quizzes.
- Quiz deleted: remove its notifications.
"""
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone


def _quiz_message(quiz):
    actor = quiz.created_by
    actor_name = (actor.full_name or actor.username) if actor else 'Giáo viên'
    return f'{actor_name} vừa công bố đề thi: "{quiz.title}"'


def _visible_quizzes(classroom_id):
    from exams.models import Quiz

    now = timezone.now()
    return (
        Quiz.objects
        .filter(
            classroom_id=classroom_id,
            is_published=True,
            assigned_to__isnull=True,
        )
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
        .select_related('created_by')
    )


def _notify_student(student_id, quiz):
    from .models import Notification

    Notification.objects.get_or_create(
        recipient_id=student_id,
        verb=Notification.VERB_PUBLISHED_QUIZ,
        target_id=quiz.id,
        defaults={
            'actor': quiz.created_by,
            'message': _quiz_message(quiz),
        },
    )


@receiver(post_save, sender='exams.Quiz')
def notify_students_on_quiz_publish(sender, instance, created, **kwargs):
    from .models import Notification

    quiz = instance
    visible = (
        quiz.is_published
        and quiz.assigned_to_id is None
        and not (quiz.publish_at and quiz.publish_at > timezone.now())
    )
    if not visible:
        Notification.objects.filter(
            verb=Notification.VERB_PUBLISHED_QUIZ,
            target_id=quiz.id,
        ).delete()
        return

    from classes.models import ClassStudent

    student_ids = ClassStudent.objects.filter(
        classroom_id=quiz.classroom_id
    ).values_list('student_id', flat=True)
    for student_id in student_ids:
        _notify_student(student_id, quiz)


@receiver(post_save, sender='classes.ClassStudent')
def notify_new_student_on_visible_quizzes(sender, instance, created, **kwargs):
    if not created:
        return
    for quiz in _visible_quizzes(instance.classroom_id):
        _notify_student(instance.student_id, quiz)


@receiver(post_delete, sender='exams.Quiz')
def remove_quiz_notifications(sender, instance, **kwargs):
    from .models import Notification

    Notification.objects.filter(
        verb=Notification.VERB_PUBLISHED_QUIZ,
        target_id=instance.id,
    ).delete()

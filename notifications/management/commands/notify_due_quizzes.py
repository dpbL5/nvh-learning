from django.core.management.base import BaseCommand
from django.utils import timezone

from classes.models import ClassStudent
from exams.models import Quiz
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Create notifications for quizzes whose publish_at time has passed.'

    def handle(self, *args, **options):
        now = timezone.now()
        quizzes = (
            Quiz.objects
            .filter(
                is_published=True,
                assigned_to__isnull=True,
                publish_at__isnull=False,
                publish_at__lte=now,
            )
            .select_related('created_by')
        )

        created_count = 0
        for quiz in quizzes:
            actor = quiz.created_by
            actor_name = (actor.full_name or actor.username) if actor else 'Giáo viên'
            message = f'{actor_name} vừa công bố đề thi: "{quiz.title}"'
            student_ids = ClassStudent.objects.filter(
                classroom_id=quiz.classroom_id
            ).values_list('student_id', flat=True)
            for student_id in student_ids:
                _, created = Notification.objects.get_or_create(
                    recipient_id=student_id,
                    verb=Notification.VERB_PUBLISHED_QUIZ,
                    target_id=quiz.id,
                    defaults={'actor': quiz.created_by, 'message': message},
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created_count} notifications.'))

from django.core.management.base import BaseCommand
from django.db import transaction

from exams.models import QuizAttempt, QuizQuestion
from exams.scoring import (
    answers_payload_from_stored,
    calculate_score,
    has_unrecoverable_true_false,
    score_submission,
)


class Command(BaseCommand):
    help = 'Recalculate completed quiz attempt scores from their saved answers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing to the database.',
        )
        parser.add_argument(
            '--attempt-id',
            type=int,
            default=None,
            help='Only regrade this attempt id.',
        )
        parser.add_argument(
            '--reset-unrecoverable',
            action='store_true',
            help=(
                'Delete answers and reopen attempts whose true/false answers predate '
                'answer_value. Those choices were never stored, so students must retake '
                'the quiz to receive a correct score.'
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reset_unrecoverable = options['reset_unrecoverable']

        attempts = (
            QuizAttempt.objects.filter(is_completed=True)
            .select_related('quiz')
            .prefetch_related(
                'answers',
                'answers__quiz_question',
                'answers__quiz_question__question',
            )
            .order_by('pk')
        )
        if options['attempt_id']:
            attempts = attempts.filter(pk=options['attempt_id'])

        questions_by_quiz = {}
        updated = unchanged = unrecoverable = reset = 0

        for attempt in attempts:
            if attempt.quiz_id not in questions_by_quiz:
                questions_by_quiz[attempt.quiz_id] = list(
                    QuizQuestion.objects.filter(quiz_id=attempt.quiz_id)
                    .select_related('question')
                    .prefetch_related('question__options')
                )
            quiz_questions = questions_by_quiz[attempt.quiz_id]
            questions_by_id = {qq.pk: qq.question for qq in quiz_questions}
            stored_answers = list(attempt.answers.all())

            if has_unrecoverable_true_false(questions_by_id, stored_answers):
                if not reset_unrecoverable:
                    unrecoverable += 1
                    continue

                self.stdout.write(
                    f'Attempt {attempt.pk}: reset for retake '
                    f'({attempt.student_id}, {attempt.quiz.title}) — legacy true/false answers.'
                )
                if not dry_run:
                    with transaction.atomic():
                        attempt.answers.all().delete()
                        attempt.score = None
                        attempt.is_completed = False
                        attempt.end_time = None
                        attempt.save(update_fields=['score', 'is_completed', 'end_time'])
                reset += 1
                continue

            payload = answers_payload_from_stored(stored_answers)
            _, earned_points, total_points = score_submission(quiz_questions, payload)
            new_score = calculate_score(earned_points, total_points)

            if new_score == attempt.score:
                unchanged += 1
                continue

            self.stdout.write(f'Attempt {attempt.pk}: {attempt.score} -> {new_score}')
            if not dry_run:
                QuizAttempt.objects.filter(pk=attempt.pk).update(score=new_score)
            updated += 1

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Updated {updated}; unchanged {unchanged}; '
            f'unrecoverable {unrecoverable}; reset {reset}.'
        ))
        if unrecoverable:
            self.stdout.write(self.style.WARNING(
                'Legacy true/false answers did not store Đúng/Sai, so their scores cannot '
                'be recomputed. Re-run with --reset-unrecoverable to let students retake '
                'those attempts.'
            ))

# Deduplicate legacy rows and add exam integrity constraints

from django.db import migrations, models
from django.db.models import Count


def deduplicate(apps, schema_editor):
    StudentAnswer = apps.get_model('exams', 'StudentAnswer')
    QuizQuestion = apps.get_model('exams', 'QuizQuestion')

    duplicate_options = (
        StudentAnswer.objects
        .filter(selected_option__isnull=False)
        .values('attempt_id', 'quiz_question_id', 'selected_option_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for group in duplicate_options:
        ids = list(
            StudentAnswer.objects.filter(
                attempt_id=group['attempt_id'],
                quiz_question_id=group['quiz_question_id'],
                selected_option_id=group['selected_option_id'],
            ).order_by('id').values_list('id', flat=True)
        )
        StudentAnswer.objects.filter(id__in=ids[1:]).delete()

    duplicate_texts = (
        StudentAnswer.objects
        .filter(selected_option__isnull=True)
        .values('attempt_id', 'quiz_question_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for group in duplicate_texts:
        ids = list(
            StudentAnswer.objects.filter(
                attempt_id=group['attempt_id'],
                quiz_question_id=group['quiz_question_id'],
                selected_option__isnull=True,
            ).order_by('id').values_list('id', flat=True)
        )
        StudentAnswer.objects.filter(id__in=ids[1:]).delete()

    duplicate_questions = (
        QuizQuestion.objects
        .values('quiz_id', 'question_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for group in duplicate_questions:
        ids = list(
            QuizQuestion.objects.filter(
                quiz_id=group['quiz_id'],
                question_id=group['question_id'],
            ).order_by('id').values_list('id', flat=True)
        )
        QuizQuestion.objects.filter(id__in=ids[1:]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0014_question_question_text_question_topic'),
    ]

    operations = [
        migrations.RunPython(deduplicate, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='quizquestion',
            constraint=models.UniqueConstraint(fields=('quiz', 'question'), name='uniq_quiz_question'),
        ),
        migrations.AddConstraint(
            model_name='studentanswer',
            constraint=models.UniqueConstraint(
                condition=models.Q(selected_option__isnull=False),
                fields=('attempt', 'quiz_question', 'selected_option'),
                name='uniq_student_answer_option',
            ),
        ),
        migrations.AddConstraint(
            model_name='studentanswer',
            constraint=models.UniqueConstraint(
                condition=models.Q(selected_option__isnull=True),
                fields=('attempt', 'quiz_question'),
                name='uniq_student_answer_text',
            ),
        ),
    ]

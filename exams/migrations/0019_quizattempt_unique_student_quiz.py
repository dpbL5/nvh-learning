from django.db import migrations, models


def dedupe_quiz_attempts(apps, schema_editor):
    QuizAttempt = apps.get_model('exams', 'QuizAttempt')
    seen = set()
    for attempt in QuizAttempt.objects.order_by('quiz_id', 'student_id', 'id').iterator():
        key = (attempt.quiz_id, attempt.student_id)
        if key in seen:
            attempt.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0018_studentanswer_answer_value'),
    ]

    operations = [
        migrations.RunPython(dedupe_quiz_attempts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='quizattempt',
            constraint=models.UniqueConstraint(
                fields=('quiz', 'student'),
                name='uniq_quiz_attempt',
            ),
        ),
    ]

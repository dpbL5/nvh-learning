from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0017_question_grade_quizquestion_is_points_overridden_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentanswer',
            name='answer_value',
            field=models.BooleanField(blank=True, help_text='Học sinh chọn Đúng (True) / Sai (False) cho từng phát biểu ở dạng Đúng/Sai.', null=True),
        ),
    ]

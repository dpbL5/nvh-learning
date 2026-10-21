# Generated manually for question heading/topic support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0013_alter_option_id_alter_question_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='question_text',
            field=models.CharField(blank=True, default='', help_text='Tiêu đề/vấn đề chính (dùng cho dạng Đúng/Sai).', max_length=500),
        ),
        migrations.AddField(
            model_name='question',
            name='topic',
            field=models.CharField(blank=True, default='', help_text='Chủ đề cụ thể.', max_length=200),
        ),
    ]

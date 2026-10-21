from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0015_exam_uniqueness_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagebank',
            name='cloudinary_public_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

# Deduplicate legacy notifications and prevent duplicate quiz notifications

from django.db import migrations, models
from django.db.models import Count


def deduplicate(apps, schema_editor):
    Notification = apps.get_model('notifications', 'Notification')

    duplicates = (
        Notification.objects
        .values('recipient_id', 'verb', 'target_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for group in duplicates:
        notifications = Notification.objects.filter(
            recipient_id=group['recipient_id'],
            verb=group['verb'],
            target_id=group['target_id'],
        ).order_by('id')
        keep = notifications.first()
        if keep:
            if notifications.filter(is_read=True).exists() and not keep.is_read:
                keep.is_read = True
                keep.save(update_fields=['is_read'])
            notifications.exclude(pk=keep.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(deduplicate, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(
                fields=('recipient', 'verb', 'target_id'),
                name='uniq_notification_recipient_target',
            ),
        ),
    ]

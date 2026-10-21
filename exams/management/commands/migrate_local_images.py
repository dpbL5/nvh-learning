import os

from django.core.management.base import BaseCommand

from ai_core.services.cloudinary_service import upload_to_cloudinary
from exams.models import ImageBank


class Command(BaseCommand):
    help = 'Upload existing locally stored ImageBank files to Cloudinary.'

    def handle(self, *args, **options):
        migrated = 0
        failed = 0
        for image_bank in ImageBank.objects.exclude(image_file=''):
            name = image_bank.image_file.name
            if name.startswith('http'):
                continue
            try:
                path = image_bank.image_file.path
            except Exception:
                failed += 1
                continue
            if not os.path.exists(path):
                failed += 1
                continue

            result = upload_to_cloudinary(path, file_name=os.path.basename(path))
            secure_url = result.get('secure_url') if result else None
            if not secure_url:
                failed += 1
                continue

            image_bank.image_file.name = secure_url
            image_bank.image_url = secure_url
            image_bank.cloudinary_public_id = result.get('public_id')
            image_bank.save(update_fields=['image_file', 'image_url', 'cloudinary_public_id'])
            migrated += 1

        self.stdout.write(self.style.SUCCESS(f'Migrated {migrated} images; {failed} failed.'))

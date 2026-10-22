"""Local regression settings; never inherit database or service credentials from .env."""
import os
import tempfile

for key in ('OPENAI_API_KEY', 'GEMINI_API_KEY', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET'):
    os.environ[key] = ''

from .settings import *  # noqa: F403,E402

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'HOST': '127.0.0.1',
    'PORT': os.environ.get('TEST_DB_PORT', '55439'),
    'NAME': 'nvh_test',
    'USER': 'nvh_test',
    'PASSWORD': 'nvh_test_local',
    'TEST': {'NAME': 'test_nvh_learning'},
}}
SECRET_KEY = 'nvh-local-test-key-only-at-least-32-characters'
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
_media = tempfile.TemporaryDirectory(prefix='nvh-test-media-')
MEDIA_ROOT = _media.name
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_CLASSES': ()}  # noqa: F405

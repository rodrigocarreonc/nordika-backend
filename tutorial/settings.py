"""Main Django and DRF settings for Nordika (local development and Azure)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-d--(jxx$$0bgni3o073%4_-uvq0v2oo27go3*5vz!^-xz&8#dh'

# Environment detection: Azure App Service mounts persistent storage at /home/site,
# so the same code works on web, SSH and local development without extra variables.
IS_PRODUCTION = os.path.exists('/home/site')

DEBUG = not IS_PRODUCTION

if IS_PRODUCTION:
    ALLOWED_HOSTS = ['topicos-epfmfpaxbadrghhj.mexicocentral-01.azurewebsites.net']
else:
    # Locally any host is allowed so devices on the LAN (Expo Go) can reach the API.
    ALLOWED_HOSTS = ['*']

# Trusted CSRF origins for the Django admin and requests from Expo Web.
CSRF_TRUSTED_ORIGINS = [
    'https://topicos-epfmfpaxbadrghhj.mexicocentral-01.azurewebsites.net',
    'http://localhost:8081',
    'http://127.0.0.1:8081',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Installed apps: Django core, CORS, DRF + tokens, filters and the domain app.
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'tutorial.quickstart',
]

# CorsMiddleware must go first to add CORS headers before other middlewares respond;
# WhiteNoise serves the Django admin static files in production without an extra web server.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tutorial.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tutorial.wsgi.application'

# On Azure the SQLite database lives in /home/site to survive restarts and redeploys.
if IS_PRODUCTION:
    DB_PATH = '/home/site/db.sqlite3'
else:
    DB_PATH = BASE_DIR / 'db.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_PATH,
    }
}

# Password strength rules applied both in Django Admin and in the auth endpoints.
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Mexican Spanish for Django validation messages (shown to users) and local time zone.
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Uploaded furniture images; in production they are stored on the persistent Azure volume.
MEDIA_URL = '/media/'
if IS_PRODUCTION:
    MEDIA_ROOT = '/home/site/media'
else:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Console email backend to inspect messages locally without configuring an external SMTP.
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# Default API policy: every endpoint requires authentication (Token for the app and
# Session for the DRF browsable API) unless it explicitly declares AllowAny.
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'tutorial.quickstart.pagination.ConfigurablePageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# Open CORS to accept requests from Expo Web, local browsers and mobile apps.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

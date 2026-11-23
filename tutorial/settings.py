"""Configuración principal de Django y DRF para Nordika (desarrollo local y Azure)."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-d--(jxx$$0bgni3o073%4_-uvq0v2oo27go3*5vz!^-xz&8#dh'

# Detección de entorno: Azure App Service monta el almacenamiento persistente en /home/site;
# así el mismo código funciona en web, SSH y desarrollo local sin variables extra.
IS_PRODUCTION = os.path.exists('/home/site')

DEBUG = not IS_PRODUCTION

if IS_PRODUCTION:
    ALLOWED_HOSTS = ['topicos-epfmfpaxbadrghhj.mexicocentral-01.azurewebsites.net']
else:
    # En local se permite cualquier host para que dispositivos en la red LAN (Expo Go) accedan al API.
    ALLOWED_HOSTS = ['*']

# Orígenes confiables para CSRF al usar el admin de Django o peticiones desde Expo Web.
CSRF_TRUSTED_ORIGINS = [
    'https://topicos-epfmfpaxbadrghhj.mexicocentral-01.azurewebsites.net',
    'http://localhost:8081',
    'http://127.0.0.1:8081',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Aplicaciones instaladas: núcleo de Django, CORS, DRF + tokens, filtros y app de dominio.
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

# CorsMiddleware debe ir primero para inyectar cabeceras CORS antes de que otros middlewares respondan;
# WhiteNoise sirve estáticos del admin de Django en producción sin servidor web adicional.
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

# En Azure la base SQLite vive en /home/site para sobrevivir a reinicios y redespliegues.
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

# Reglas de fortaleza de contraseña aplicadas tanto en Django Admin como en los endpoints de auth.
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

# Idioma español de México para mensajes de validación de Django y zona horaria local.
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Imágenes subidas de muebles; en producción se guardan en el volumen persistente de Azure.
MEDIA_URL = '/media/'
if IS_PRODUCTION:
    MEDIA_ROOT = '/home/site/media'
else:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Correo en consola para inspeccionar envíos en local sin configurar SMTP externo.
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# Política por defecto de la API: todo endpoint exige autenticación (Token para la app y
# Session para el navegador de DRF) salvo los que declaren AllowAny explícitamente.
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

# CORS abierto para aceptar peticiones desde Expo Web, navegadores locales y apps móviles.
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

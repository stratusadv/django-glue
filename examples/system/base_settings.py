import os
from pathlib import Path

SITE_ID = 1

ADMINS = [
    ('Wesley Howery', 'wesleyh@stratusadv.com'),
    ('Austin Sauer', 'austins@stratusadv.com'),
]

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')

INTERNAL_IPS = ('127.0.0.1',)

BASE_DIR = str(Path(__file__).parent.parent)

if os.getenv('DJANGO_DEBUG', 'False') == 'True':
    DEBUG = True
else:
    DEBUG = False

MAINTENANCE_MODE = bool(int(os.getenv('MAINTENANCE_MODE', 0)))

# Email Settings
EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
SENDGRID_SANDBOX_MODE_IN_DEBUG = False
SENDGRID_TEMPLATE_ID = False
DEFAULT_FROM_EMAIL = 'Stratus ADV <noreply@stratusadv.com>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
]

INSTALLED_APPS += [
    'crispy_forms',
    'crispy_bootstrap5',
    'django_flatpickr',
    'django_glue',
    'debug_toolbar',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Login Settings
LOGIN_URL = 'config:auth:login'

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/
USE_I18N = True
LANGUAGE_CODE = 'en-us'

USE_TZ = True
TIME_ZONE = 'America/Edmonton'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = os.getenv('DJANGO_STATIC_URL', '/static/')

if not DEBUG:
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
else:
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "static"),
    ]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

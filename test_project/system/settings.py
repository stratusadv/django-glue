import logging
import os
import sys

logging.basicConfig(
    format='[%(asctime)-15s] Django Glue: "%(message)s"',
    datefmt='%d/%b/%Y %H:%M:%S'
)

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

WSGI_APPLICATION = 'test_project.system.wsgi.application'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'django_glue',
]

INSTALLED_APPS += [
    'test_project.app.capability',
    'test_project.app.fight',
    'test_project.app.fight.round',
    'test_project.app.gorilla',
    'test_project.app.gorilla.capability',
    'test_project.app.home',
    'test_project.app.training',
]

INSTALLED_APPS += [
    'test_project.developer.form',
    'test_project.developer.field',
]

INSTALLED_APPS += [
    'django_spire.core',
    'django_spire.theme',
    'django_spire.history',
    'django_spire.contrib.seeding',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_glue.middleware.DjangoGlueMiddleware',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'test_project.db',
    }
}

ROOT_URLCONF = 'test_project.system.urls'

SECRET_KEY = 'django_glue_secret_key_of_secrets'

USE_TZ = True
TIME_ZONE = 'America/Edmonton'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'test_project/templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django_glue.context_processors.django_glue',
                'django_spire.core.context_processors.django_spire',
            ],
            'builtins': [
                'django_spire.core.templatetags.spire_core_tags',
                'django_spire.contrib.pagination.templatetags.pagination_tags',
            ],
            'debug': DEBUG,
        },
    },
]

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'test_project/static')]

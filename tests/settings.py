import os
import logging

logging.basicConfig(
    format='[%(asctime)-15s] Django Glue: "%(message)s"',
    datefmt='%d/%b/%Y %H:%M:%S'
)

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1']

WSGI_APPLICATION = 'tests.wsgi.application'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.admin',
    'django_glue',
    'tests',
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

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'django_glue_test.db',
    }
}

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django_glue.middleware.GlueMiddleware'
)

ROOT_URLCONF = 'tests.urls'

SECRET_KEY = 'django_glue_secret_key_of_secrets'

USE_TZ = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django_glue.context_processors.glue',
            ],
            'builtins': [
            ],
            'debug': DEBUG,
        },
    },
]

STATIC_URL = 'static/'

DJANGO_GLUE_URL = 'django_glue/'
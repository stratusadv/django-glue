from system.base_settings import *
from system.development.settings import INSTALLED_APPS

ROOT_URLCONF = 'system.testing.urls'
ALLOWED_HOSTS = ['127.0.0.1']

TEST_DB_NAME = BASE_DIR + '/testing.db'

DATABASES = {
    'default': {
        'NAME': TEST_DB_NAME,
        'ENGINE': 'django.db.backends.sqlite3',
        'TEST': {
            'NAME': TEST_DB_NAME,
        }
    }
}

WSGI_APPLICATION = 'system.testing.wsgi.application'

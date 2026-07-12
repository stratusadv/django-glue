from test_project.settings import *  # noqa: F403


ROOT_URLCONF = 'test_project.urls'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']

TESTING_DB_NAME = str(BASE_DIR / 'testing.db')  # noqa: F405

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': TESTING_DB_NAME,
        'TEST': {
            'NAME': TESTING_DB_NAME,
        },
    },
}

WSGI_APPLICATION = 'test_project.wsgi.application'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

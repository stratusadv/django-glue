# Installation

Start by install django-glue using pip.

```
pip install django_glue
```

Add django-glue to your installed apps in your project settings. 
We recommend adding it below the other installed applications.

```python
INSTALLED_APPS = [
    ...
    'django_glue',
]
```

Add django-glue middleware to your project settings.

```python
MIDDLEWARE_CLASSES = (
    ...
    'django_glue.middleware.GlueMiddleware',
)

```

Add django-glue context processor to your project settings.

```python
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'django_glue.context_processors.glue',
            ],
        },
        ...
    },
]
```
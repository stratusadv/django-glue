# django-glue

We built Django Glue to help solve the problem of fluid interactions between the front and back ends of a Django application.

This project is in prototype phase please look at the tests directory of this code base for examples and instructions.

Our end goal is to bring as much front end power to the Django framework as possible while remaining pythonic.

## Requirements

- Django 3.2+ or 4.0+
- Python 3.8+

## Installation

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

## Roadmap

- [ ] Prototype (2022-07-31)

## Authors

- Nathan Johnson
- Wesley Howery
# django-glue

We built Django Glue to help solve the problem of fluid interactions between the front and back ends of a Django application.
Our end goal is to bring as much front end power to the Django framework as possible while remaining pythonic.

This project is in prototype phase please look at the tests directory of this code base for examples and instructions.

## Why?

We are active web platform developers that want to provide our clients with the best user experience without having to learn a bunch of different technology stacks.
Django glue allows us to do fancy javascript like page interactions and updates while remaining in the comfort of our django/python world.

Education is also a big part of what we do and our focus is on teaching our people python, so they can focus on data science and automation and make solid interfaces! 

## Requirements

- Django 3.2+ or 4.0+
- Python 3.8+

## Dependencies

- Alpine JS
- Axios

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

- [x] Prototype (2022-07-12)
- [ ] Alpha (2022-08-31)
- [ ] Beta (2023-06-31)

## Authors

- Nathan Johnson
- Wesley Howery
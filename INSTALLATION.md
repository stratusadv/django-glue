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

Add the required template tags to your base template

```html
{% load django_glue %}

<!doctype html>

<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, user-scalable=no, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>Base</title>
</head>

<body>

<!-- Your Content Above the Glue Initialization-->

{% glue_init %}

</body>

</html>
```
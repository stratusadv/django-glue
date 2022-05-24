# django-glue

We built Django Glue to help solve the problem of fluid interactions between the front and back ends of a Django application.

A single function call in a view allows you to interact with a model object or specific field in both the context data and javascript throught a context json object. 
This handles construction of the data the connection between all sides along with the ability to update the model object automatically.

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

Migrate django-glue by running the following command.

```
python manage.py migrate
```

After all the migrations are successfully complete you are ready to go.

## Getting Started

Inside of the view you would like to have access to glue objects simply include and call the glue method.

```python
from django_glue.utils import add_glue

# Simply call this function to allow access to this object.
add_glue(model_object=test_model, method='write')

# Including the field will restrict access to only that field name.
add_glue(model_object=test_model, method='write', field_name='text')
```

Example View 

```python
from django.views.generic import TemplateView

from tests.models import TestModel

from django_glue.utils import add_glue


class TestView(TemplateView):
    template_name = 'test.html'

    # We use the context data override as a convenient location to create glue connections.
    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        # Example Model Object
        test_model = TestModel.objects.create(
            char='Some Characters',
            text='Alot of text goes into this text field to be tested and manipulated',
            integer=789456123,
            decimal=258.369,
        )

        # Simply call this function to allow access to this object.
        add_glue(model_object=test_model, method='write')

        # Including the field will restrict access to only that field name.
        add_glue(model_object=test_model, method='write', field_name='text')

        return context_data
```

Template Context Data Ouput

```python
glue = {
  "fields": {
    "test_model": {
      "django_glue_key": "d44c4b3e-bcd1-4419-9276-3f5830ee860c",
      "text": "Alot of text goes into this text field to be tested and manipulated"
    }
  },
  "objects": {
    "test_model": {
      "django_glue_key": "bd452caf-211b-419c-a7cf-7f567036e464",
      "data": <TestModel: Some Characters>,
    }
  }
}
```

Javascript Json Data Output

```javascript
glue = {
  "fields": {
    "test_model": {
      "django_glue_key": "d44c4b3e-bcd1-4419-9276-3f5830ee860c",
      "text": "Alot of text goes into this text field to be tested and manipulated"
    }
  },
  "objects": {
    "test_model": {
      "django_glue_key": "bd452caf-211b-419c-a7cf-7f567036e464",
      "char": "Some Characters",
      "text": "Alot of text goes into this text field to be tested and manipulated",
      "integer": 789456123,
      "decimal": 258.369
    }
  }
}
```

Updating the Javascript JSON Object will automatically update the model in the Django backend.

## Roadmap

- [ ] Prototype (2022-07-31)

## Authors

- Nathan Johnson
- Wesley Howery
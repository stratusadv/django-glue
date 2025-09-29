# ModelObjectGlue Guide

## Purpose

ModelObjectGlue allows the user to access Django Model objects from the front end.


### When to use

- When you need to access to a Django Model object for front end functionality.
    - Ex: Glueing a Django Model object in order to access the fields using django glue form.

### When not to use

- When you need view access to a Django Models fields.
    - This should simply be passed down in the context data.


## Shortcut Method

::: django_glue.shortcuts.****glue_mo****del_object


## How To Use

1. Import `django_glue`.
``` python
import django_glue as dg
```

2. Get the Django Model Object you need access to on the front end.
``` python
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    person = Person.objects.get(pk=pk)
```

3. Use the shortcut method `glue_model_object(request, <str:unique_name>)` to glue the model object to the glue session data.
``` python
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    person = Person.objects.get(pk=pk)
    
    dg.glue_model_object(request=request, unique_name='person')
    
    ... update form logic ...
```

4. On the front end using AlpineJS, initialize a new glue model object with the same unique name you specified in step 3.
```html
<div 
    x-data="{
        person: new ModelObjectGlue('person')
    }"
></div>
```

5. Call the `get` method on the glue model object to retrieve the Django Model Object's data from the session data.
```html
<div 
    x-data="{
        person: new ModelObjectGlue('person'),
        async init() {
            await this.person.get()
        }
    }"
></div>
```

### Full Example

#### Back End

``` python title="app/person/views.py"
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    person = Person.objects.get(pk=pk)
    
    dg.glue_model_object(request=request, unique_name='person')
    
    ... update form logic ...
    
    return TemplateResponse(
        request=request,
        template='person/form/update_form.html',
        context={
            'person': person  # Used by the form url.
        }
    )
```

#### Front End

```html title="templates/person/person_form.html"
<form
    method="POST"
    action="{% url 'person:form:update_form' pk=person.pk %}"
    x-data="{
        person: new ModelObjectGlue('person')
        async init() {
            await this.person.get()
        }
    }"
    ... update form html ...
></form>
```

### More Information

See [ModelObjectGlue](http://django-glue.stratusadv.com/api/javascript/model_object_glue/) 
for the different methods available for ModelObjectGlue objects on the front end.

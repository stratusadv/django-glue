# GlueCharField Guide

## Purpose

GlueCharField allows the user to add an extra input field other than Django Model objects on the front end.

### When to use

- When you need an extra field to create a foreign object to Django Model object on the front end.
    - Ex: Creating a new Child object and selecting a Parent object using django glue form.

## How To Use

1. Import `django_glue`.
```python
import django_glue as dg
```

2. Get the Django Model Object you need access to on the front end.
```python
import django_glue as dg

from django.shortcuts import get_object_or_404
from django_spire.core.shortcuts import get_object_or_null_obj

from app.parent.child.models import Child


def child_create_form_view(request):
    child = get_object_or_null_obj(Child, pk=0)
```

3. Use the shortcut method `glue_model_object(request, <str:unique_name>)` to glue the model object to the glue session data.
```python
import django_glue as dg

from django.shortcuts import get_object_or_404
from django_spire.core.shortcuts import get_object_or_null_obj

from app.parent.models import Parent # Add Parent model
from app.parent.child.models import Child


def child_create_form_view(request):
    child = get_object_or_null_obj(Child, pk=0)
    
    dg.glue_model_object(request=request, unique_name='child', model_object=child)
    
    ... update form logic ...
    
    return TemplateResponse(
        request=request,
        template='child/form/create_form.html',
        context={
            'parent_choices': json.dumps(
                Parent.objects.values_list('pk', 'name')
            ),
        }
    )
```

4. On the front end using AlpineJS, initialize a new glue model object with the same unique name you specified in step 3. Add the glue char field parent in the init() method. Set the choices for the glue char field parent.
```html
<form
    x-data="{
        async init () {
            await this.child.get()
            this.child.glue_fields.parent.choices = {{ parent_choices }}
        },
        child: new ModelObjectGlue('child')
        parent: new GlueCharField('parent')
    }"
>
    
</form>
```

### Full Example

### Implementing Glue Char Field to update data

Goal: Display and edit child’s record on the form

Approach: Initialize `child` using `ModelObjectGlue` and call `get()` inside `init()` to get all the data from backend.

##### Back End:

```python title="app/parent/child/urls.py"
from django.urls import path

from app.parent.child.views import form_views


app_name = 'form'

urlpatterns = [
    path('<int:parent_pk>/<int:pk>/update/', form_views.update_form_view, name='update'),
]

```

```python  title="app/parent/child/views.py"
import django_glue as dg

from django.shortcuts import get_object_or_404
from django_spire.core.shortcuts import get_object_or_null_obj

from app.parent.models import Parent
from app.parent.child.models import Child


def child_update_form_view(request, pk, parent_pk):
    parent = get_object_or_404(Parent, pk=parent_pk)
    child = get_object_or_null_obj(Child, pk=pk)

    dg.glue_model_object(request=request, unique_name='child', model_object=child)

    if request.method == 'POST':
        # parent_pk is used to set the parent of the child in the form
        form = forms.ChildForm(request.POST, instance=child)
        # ... the rest of the update form logic ...

    return TemplateResponse(
        request=request,
        template='parent/child/form/update_form.html',
        context={
            'parent': parent,
            'parent_choices': json.dumps(
                sorted(
                    [(str(parent.id), parent.get_full_name()) for parent in Parent.objects.all()]
                )
            ),
        }
    )
```

##### Front End:

```html title="templates/person/person_form.html"

<form
    method="POST"
    action="{% url 'parent:child:form:update' parent_pk=person.pk %}"
    x-data="{
        async init() {
            await this.child.get()
            this.parent.choices = {{ parent_choices }}
            this.parent.value = {{ parent.pk }}
        },
        child: new ModelObjectGlue('child'),
        parent: new GlueCharField('parent')
    }"
>
    {% csrf_token %}
    {% include 'django_glue/form/field/char_field.html' with glue_char_field='parent' %}
    {% include 'django_glue/form/field/char_field.html' with glue_model_field='child.full_name' %}
    {% include 'core/form/button/form_submit_button.html' with button_text='Save' %}
</form>
```

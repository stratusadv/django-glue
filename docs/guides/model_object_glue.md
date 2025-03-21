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

::: django_glue.shortcuts.glue_model_object


## How To Use

1. Import `django_glue`.
``` python
import django_glue as dg
```
2. Get the Django Model Object you need access to on the front end.
3. Use the shortcut method `glue_model_object(request, <str:unique_name>)` to glue the model object to the glue session data.
4. On the front end using AlpineJS, initialize a new glue model object with the same unique name you specified in step 3.
```html
<div 
    x-data="{
        example_model_object: new GlueModelObject('<str:unique_name>')
    }"
></div>
```
5. Call the `get` method on the glue model object to retrieve the Django Model Object's data from the session data.
```html
<div 
    x-data="{
        example_model_object: new GlueModelObject('<str:unique_name>'),
        async init() {
            this.example_model_object = await this.example_model_object.get()
        }
    }"
></div>
```

### Example

#### Back End

``` python
import django_glue as dg

def person_update_form_view(request, pk):
    person = Person.objects.get(pk=pk)
    
    dg.glue_model_object(
        request=request,
        unique_name='person',
        fields=['name']
    )
    
    ... update form logic ...
    
    return TemplateResponse(
        request=request,
        template='person/update_form.html',
        context={
            'person': person  # Used by the form url.
        }
    )
```

#### Front End

```html
<form
    method="POST"
    action="{% url 'person:form:update_form' pk=person.pk %}"
    x-data="{
        person: new GlueModelObject('person')
        async init() {
            this.person = await this.person.get()
        }
    }"
    ... update form html ...
></form>
```


[//]: # (Include method and link to JS object for more uses on the front end)

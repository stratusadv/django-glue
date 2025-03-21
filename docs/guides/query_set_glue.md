# QuerySetGlue Guide

## Purpose

QuerySetGlue allows the user to access a Django QuerySet from the front end.


### When to use

- When you need to access to multiple Django Model objects for front end functionality.
    - Ex: Glueing a Django QuerySet in order to select one from a glue select field.

### When not to use

- When jinja templates can also complete what you need to do.
    - Ex: Looping over a Django QuerySet to display information. 


## Shortcut Method

::: django_glue.shortcuts.glue_query_set


## How To Use

1. Import `django_glue`.
``` python
import django_glue as dg
```
2. Get the Django QuerySet you need access to on the front end.
3. Use the shortcut method `glue_queryset_object(request, <str:unique_name>, <QuerySet:query_set>)` to glue the model objects in the query set to the glue session data.
4. On the front end using AlpineJS, initialize a new glue query set with the same unique name you specified in step 3.
```html
<div 
    x-data="{
        example_model_object: new GlueQuerySet('<str:unique_name>')
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

### More Information

See [ModelObjectGlue](http://django-glue.stratusadv.com/api/javascript/model_object_glue/) 
for the different methods available for Glue Model Objects on the front end.

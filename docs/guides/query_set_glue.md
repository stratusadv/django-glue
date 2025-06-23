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
``` python
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    adults = Person.objects.filter(age > 17)
```

3. Use the shortcut method `glue_queryset_object(request, <str:unique_name>, <QuerySet:query_set>)` to glue the model objects in the query set to the glue session data.
``` python
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    adults = Person.objects.filter(age > 17)
    
    dg.glue_query_set(request=request, unique_name='adults', target=adults)
    
    ... update form logic ...
```

4. On the front end using AlpineJS, initialize a new glue query set with the same unique name you specified in step 3.
```html
<div 
    x-data="{
        adult_query_set: new GlueQuerySet('adults')
    }"
></div>
```
5. Call the `all` method on the glue query set to retrieve the data from the Django Model Objects in the query set.
```html
<div 
    x-data="{
        adults: [],
        adult_query_set: new GlueQuerySet('adults'),
        async init() {
            this.adults = await this.adult_query_set.all()
        }
    }"
></div>
```

### Full Example

#### Back End

``` python
import django_glue as dg

from app.people.models import Person


def person_update_form_view(request, pk):
    adults = Person.objects.filter(age > 17)
    
    dg.glue_query_set(request=request, unique_name='adults', target=adults)
    
    ... update form logic ...
    
    return TemplateResponse(
        request=request,
        template='person/form/update_form.html',
        context={}
    )
```

#### Front End

```html
<div 
    x-data="{
        adults: [],
        adult_query_set: new GlueQuerySet('adults'),
        async init() {
            this.adults = await this.adult_query_set.all()
        }
    }"
></div>
```

### More Information

See [QuerySetGlue](http://django-glue.stratusadv.com/api/javascript/query_set_glue/) 
for the different methods available for QuerySetGlue objects on the front end.

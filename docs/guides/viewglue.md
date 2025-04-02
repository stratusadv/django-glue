# ViewGlue Guide

## Purpose
ViewGlue allows the user to dynamically render a template given a endpoint.

### When to use
use here

### When not to use
dont use here

## render_inner
This example will show you how to reload a page with sent information.

### How To Use
1. Import `django_glue`.
``` python
import django_glue as dg
```

2. Get the Django Model Object you need access to on the front end.
``` python
import django_glue as dg

from app.people.models import Person


def person_dashboard_content_view(request):
    body = process_request_body(request, key=None)
    selected_person = body.get('person')
    
    ... edit person data however you like ...
    ... once done send the data back to the template ...
```

3. On the front end using AlpineJS, initialize a new ViewGlue object with the url you would like to send the information to.
```html
<div 
    x-data="{
    async reload_page() {
        glue_view: new GlueView('url')
        await glue_view.render_inner(this.$refs.person_dashboard_content)
    }
    }"
    x-ref="person_dashboard_content"
>
    Dashboard content!
</div>
```

4. Call the `render_inner` method on the ViewGlue object to retrieve the Django Model Object's data from the session data.
```html
<div 
    x-data="{
        async reload_page() {
            glue_view: new GlueView('url')
        await glue_view.render_inner(this.$refs.person_dashboard_content)
        }
    }"
    x-ref="person_dashboard_content"
>
    Dashboard content!
</div>
```

### Full Example

#### Back End


#### Front End


### More Information
see [ViewGlue](http://django-glue.stratusadv.com/api/javascript/view_glue/)
for the different methods available for ViewGlue objects on the front end.

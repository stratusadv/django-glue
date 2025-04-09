# ViewGlue Guide

##In Progress

## Purpose
ViewGlue allows the user to dynamically render a template given a endpoint.

### When to use
When we want to replace/change the information inside an element.

### When not to use
We want to replace the element itself with new information

## render_inner
This example will show you how to reload a page with sent information.

### How To Use

1. Set up or decide on an endpoint for your ViewGlue object.
``` python
import django_glue as dg

from app.people.models import Person


def person_dashboard_content_view(request):
    body = process_request_body(request, key=None)
    selected_person = body.get('person')
    
    ... edit person data however you like ...
    ... once done send the data back to the template ...
```

2. On the front end using AlpineJS, initialize a new ViewGlue object with the endpoint you would like to send the information to.
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

3. Call the `render_inner` method on the ViewGlue object to render the information inside the current element. (In the below example the information in the div will be replaced)
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
In this example we are reloading the page based on a different person being selected.

#### Back End

``` python title="app/person/views.py"
def person_dashboard_content_view(request):
    body = process_request_body(request, key=None)
    selected_person = body.get('person')
    
    ... edit person data however you like ...
    
    return TemplateResponse(
        request=request,
        template='person/page/person_dashboard_page.html',
        context={
            'selected_person': selected_person  # Used by the front end to pass newly updated information
        }
    )
```

#### Front End

```html
<div 
    x-data="{
        async reload_page() {
            glue_view: new GlueView('url') // The url is the end point you want to send information to
        await glue_view.render_inner(this.$refs.person_dashboard_content)
        }
    }"
    x-ref="person_dashboard_content"
>
    Dashboard content!
</div>
```

### More Information
see [ViewGlue](http://django-glue.stratusadv.com/api/javascript/view_glue/)
for the different methods available for ViewGlue objects on the front end.

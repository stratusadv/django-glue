# ViewGlue Guide

## Purpose
ViewGlue allows the user to dynamically render a template given an endpoint.

### When to use
- Reduce HTML loading
- Easily update data on the front end dynamically
- Separating out context data for different elements in a page.

### When not to use
- Only need to hide a small amount of data
- Basic template implementation 


## How To Use
ViewGlue will be implemented inside Alpine JS's x-data.

```html
<div
    x-ref="person_item"
    x-data="{
        async init() {
            await this.person_info_detail_view()
        },
        person_info_detail_view: new ViewGlue('{% url "person:template:detail" pk=person.pk %}'),
    }"
>
</div>
```

### Full Example

### Using ViewGlue to render a person's information.

Goal: To load dynamically a person's information.

Approach: Initialize a new ViewGlue object with the endpoint to the person's information template.

```html
<div
    x-ref="person_item"
    x-data="{
        async init() {
            try {
                await this.view_person()
            } catch (e) {
                console.error(e)
            }
        },
        async view_person() {
            this.person_info_detail_view.render_outer(this.$refs.person_item)
        },
        person_info_detail_view: new ViewGlue('{% url "person:template:detail" pk=person.pk %}'),
    }"
>
    <button @click="view_person()">View this person</button>
</div>
```

### More Information
see [ViewGlue](http://django-glue.stratusadv.com/api/javascript/view_glue/)
for the different methods available for ViewGlue objects on the front end.

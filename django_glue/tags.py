from django.template.defaulttags import register


@register.inclusion_tag('django_glue/javascript.html', takes_context=True)
def django_glue(context):
    return {
        'something': 'else',
    }
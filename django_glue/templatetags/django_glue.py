from django import template

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def django_glue_init(context):
    return context
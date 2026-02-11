from django import template

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def glue_init(context, glue_js_url):
    context['glue_js_url'] = glue_js_url

    return context
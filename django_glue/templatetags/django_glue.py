from django import template

register = template.Library()


@register.inclusion_tag('django_glue/django_glue.html', takes_context=True)
def glue_init(context):
    return context


@register.inclusion_tag('django_glue/django_glue_bootstrap_css.html')
def glue_bootstrap_css(): ...


@register.inclusion_tag('django_glue/django_glue_bootstrap_js.html')
def glue_bootstrap_js(): ...


@register.inclusion_tag('django_glue/django_glue_alpine_js.html')
def glue_alpine_js(): ...
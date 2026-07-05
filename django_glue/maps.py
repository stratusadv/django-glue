from django_glue.proxies import (
    GlueModelInstanceProxy,
    GlueFormProxy,
    GlueModelFormProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
    GlueFunctionProxy,
)


SUBJECT_TYPE_TO_PROXY_CLASS = {
    'Model': GlueModelInstanceProxy,
    'ModelForm': GlueModelFormProxy,
    'QuerySet': GlueQuerySetProxy,
    'BaseForm': GlueFormProxy,
    'Template': GlueTemplateProxy,
    'Function': GlueFunctionProxy,
}

from django_glue.proxies import (
    GlueModelProxy,
    GlueFormProxy,
    GlueModelFormProxy,
    GlueQuerySetProxy,
    GlueTemplateProxy,
    GlueFunctionProxy,
)


SUBJECT_TYPE_TO_PROXY_TYPE = {
    'Model': GlueModelProxy,
    'ModelForm': GlueModelFormProxy,
    'QuerySet': GlueQuerySetProxy,
    'BaseForm': GlueFormProxy,
    'Template': GlueTemplateProxy,
    'Function': GlueFunctionProxy,
}

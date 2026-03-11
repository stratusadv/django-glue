from django_glue.proxies import GlueModelProxy, GlueFormProxy, GlueQuerySetProxy


SUBJECT_TYPE_TO_PROXY_TYPE = {
    'Model': GlueModelProxy,
    'QuerySet': GlueQuerySetProxy,
    'BaseForm': GlueFormProxy,
}
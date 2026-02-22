from django_glue.proxies import GlueModelProxy, GlueFormProxy
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy


SUBJECT_TYPE_TO_PROXY_TYPE = {
    'Model': GlueModelProxy,
    'QuerySet': GlueQuerySetProxy,
    'BaseForm': GlueFormProxy,
}
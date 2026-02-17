DJANGO_GLUE_SESSION_PROXY_KEY = 'django_glue_proxies'
DJANGO_GLUE_SESSION_KEEP_LIVE_KEY = 'django_glue_keep_live'

DJANGO_GLUE_KEEP_LIVE_INTERVAL_TIME_SECONDS = 120

DJANGO_GLUE_TYPE_CONFIG = {
    'Model': {
        'proxy_classes': {
            'server': 'django_glue.proxies.model.proxy.GlueModelProxy',
        }
    },
    'QuerySet': {
        'proxy_classes': {
            'server': 'django_glue.proxies.queryset.proxy.GlueQuerySetProxy',
        }
    }
}
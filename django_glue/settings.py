DJANGO_GLUE_SESSION_NAME = 'django_glue'

DJANGO_GLUE_KEEP_LIVE_SESSION_NAME = 'django_glue_keep_live'

DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS = 120.0

DJANGO_GLUE_TYPE_CONFIG = {
    'Model': {
        'proxy_classes': {
            'server': 'django_glue.proxies.model.proxy.GlueModelProxy',
        }
    }
}
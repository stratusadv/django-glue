from django.urls import resolve

from django_glue.session import GlueSession, GlueKeepLiveSession


class GlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Todo: Conditional statement to not clean data on keep live path
        # Doesn't run on keep live or handler

        current_url = resolve(request.path_info).url_name

        if current_url not in ['django_glue_data_handler', 'django_glue_keep_live_handler']:
            glue_session = GlueSession(request)
            glue_keep_live_session = GlueKeepLiveSession(request)
            glue_session.clean(glue_keep_live_session.clean_and_get_expired_unique_names())

        response = self.get_response(request)

        return response

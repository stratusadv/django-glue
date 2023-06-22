from django.urls import resolve

from django_glue.sessions import GlueSession, GlueKeepLiveSession


class GlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    @staticmethod
    def process_view(request, view_func, view_args, view_kwargs):
        current_url = resolve(request.path_info).url_name

        if current_url != 'django_glue_handler':
            glue_session = GlueSession(request)
            glue_keep_live_session = GlueKeepLiveSession(request)

            glue_session.clean(glue_keep_live_session.clean_and_get_expired_unique_name_set())

        return None

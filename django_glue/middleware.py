from django.urls import resolve

from django_glue.session import Session, KeepLiveSession


class DjangoGlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_url = resolve(request.path_info).url_name

        if current_url not in ['django_glue_data_handler', 'django_glue_keep_live_handler']:
            session = Session(request)
            keep_live_session = KeepLiveSession(request)
            session.clean(keep_live_session.clean_and_get_expired_unique_names())

        response = self.get_response(request)

        return response

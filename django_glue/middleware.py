from django.urls import resolve

from django_glue.session import GlueSession, GlueKeepLiveSession


class GlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        glue_session = GlueSession(request)
        glue_keep_live_session = GlueKeepLiveSession(request)
        glue_session.clean(glue_keep_live_session.clean_and_get_expired_unique_names())

        return response

    @staticmethod
    def process_view(request, view_func, view_args, view_kwargs):
        """
            Middleware to clean session data on every click...
            Right now the clean runs and then the variables get added to the session. I think this is causing us to loose
            Unique names. The Unique names should be updated then removed.
            Add glue -> Purges old data & adds itself. -> Updates itself in keep live. -> Then remove old data.
        """

        return None

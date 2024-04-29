from django_glue.conf import settings


def django_glue_context_data(request) -> dict:
    context_data = {
        'django_glue_session_data': request.session.get(
            settings.DJANGO_GLUE_SESSION_NAME,
            {}
        ),
        'django_glue_keep_live_session_data': request.session.get(
            settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME,
            {}
        ),

    }

    return context_data

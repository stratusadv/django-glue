import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.core.decorators import require_content_types, require_query_method
from django_glue.data_classes import GlueBodyData
from django_glue.handlers import GlueRequestHandler
from django_glue.responses import generate_json_404_response
from django_glue.sessions import GlueKeepLiveSession, GlueSession


@require_http_methods(["POST"])
@require_content_types('application/json', 'text/html')
def glue_data_ajax_handler_view(request):
    glue_session = GlueSession(request)
    glue_body_data = GlueBodyData(request.body)

    if glue_session.has_unique_name(glue_body_data.unique_name):
        logging.warning(request.body.decode('utf-8'))
        return GlueRequestHandler(glue_session, glue_body_data).process_response()
    else:
        return generate_json_404_response()


def glue_keep_live_handler_view(request):
    data = json.loads(request.body.decode('utf-8'))
    unique_names = data['unique_names']

    GlueKeepLiveSession(request).update_unique_names(unique_names)

    return JsonResponse(
        data=GlueSession(request).session
    )


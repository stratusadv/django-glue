import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.core.decorators import require_content_types
from django_glue.handler.body_data import GlueBodyData
from django_glue.handler.utils import process_glue_request
from django_glue.response.responses import generate_json_404_response
from django_glue.session import GlueKeepLiveSession, GlueSession


@require_http_methods(["POST"])
@require_content_types('application/json', 'text/html')
def glue_data_ajax_handler_view(request):
    glue_session = GlueSession(request)
    glue_body_data = GlueBodyData(request.body)

    if glue_body_data.unique_name in glue_session.session:
        logging.warning(request.body.decode('utf-8'))
        return process_glue_request(glue_session, glue_body_data).to_django_json_response()
    else:
        return generate_json_404_response()


def glue_keep_live_handler_view(request):
    data = json.loads(request.body)
    unique_names = data.get('unique_names', [])

    if len(unique_names) > 0:
        GlueKeepLiveSession(request).update_unique_names(unique_names)

    return JsonResponse(
        data=GlueSession(request).session
    )


def glue_session_data_view(request):
    glue_session = GlueSession(request)
    return JsonResponse(
        data=glue_session.session
    )



import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.core.decorators import require_content_types
from django_glue.handler.body import RequestBody
from django_glue.handler.utils import process_request
from django_glue.response.responses import generate_json_404_response
from django_glue.session import KeepLiveSession, Session


@require_http_methods(["POST"])
@require_content_types('application/json', 'text/html')
def handler_ajax_view(request):
    session = Session(request)
    request_body = RequestBody(request.body)

    if request_body.unique_name in session.session:
        logging.warning(request.body.decode('utf-8'))
        return process_request(session, request_body).to_django_json_response()
    else:
        return generate_json_404_response()


def keep_live_handler_ajax_view(request):
    data = json.loads(request.body)
    unique_names = data.get('unique_names', [])

    if len(unique_names) > 0:
        KeepLiveSession(request).update_unique_names(unique_names)

    return JsonResponse(
        data=Session(request).session
    )


def session_data_ajax_view(request):
    session = Session(request)
    return JsonResponse(
        data=session.session
    )



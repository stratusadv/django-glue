import json

from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods

from django_glue.decorators import require_content_types
from django_glue.glue.enums import GlueType
from django_glue.handler.data import GlueRequestData
from django_glue.handler.utils import process_request
from django_glue.response.responses import generate_json_404_response
from django_glue.session import KeepLiveSession, Session
from django_glue.settings import DJANGO_GLUE_SESSION_NAME


@require_http_methods(["POST"])
@require_content_types('application/json', 'text/html')
def handler_ajax_view(request: HttpRequest) -> JsonResponse:

    request_data = GlueRequestData(**json.loads(request.body.decode('utf-8')))
    glue_type = GlueType(request_data.glue_type)

    action = glue_type.action_type(request_data.action)
    action_kwargs = action.action_kwargs_type(**request_data.action_kwargs)
    glue_obj = glue_type.glue_class(
        request.session[DJANGO_GLUE_SESSION_NAME][request_data.unique_name]
    )


    if request_body.unique_name in session.session:
        return process_request(session, request_body).to_django_json_response()
    else:
        return generate_json_404_response()


def keep_live_handler_ajax_view(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)
    unique_names = data.get('unique_names', [])

    if len(unique_names) > 0:
        KeepLiveSession(request).update_unique_names(unique_names)

    return JsonResponse(
        data=Session(request).session
    )


def session_data_ajax_view(request: HttpRequest) -> JsonResponse:
    session = Session(request)
    return JsonResponse(
        data=session.session
    )



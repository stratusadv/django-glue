import json

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods

from django_glue.session import KeepLiveSession
from django_glue.session import GlueSession
from django_glue import data_transfer_objects as dto


@require_http_methods(['POST'])
def action_view(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.content_type != 'application/json':
        return HttpResponse(
            f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain'
        )

    try:
        data = json.loads(request.body.decode('utf-8'))
    except ValueError:
        return HttpResponse(
            'Invalid JSON',
            status=400,
            content_type='text/plain'
        )

    request_data = dto.GlueRequestData(**data)
    glue = GlueSession(request).get_glue_by_unique_name(request_data.unique_name)

    return JsonResponse(glue.process_request_data(request_data))


def keep_live_view(request: HttpRequest) -> JsonResponse:
    data = json.loads(request.body)
    unique_names = data.get('unique_names', [])

    if len(unique_names) > 0:
        KeepLiveSession(request).update_unique_names(unique_names)

    return JsonResponse(
        data=GlueSession(request).session
    )


@require_http_methods(['GET'])
def session_data_view(request: HttpRequest) -> JsonResponse:
    session = GlueSession(request)
    return JsonResponse(
        data=session.session
    )



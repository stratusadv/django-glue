from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods

from django_glue.session import GlueSession
from django_glue import data_transfer_objects as dto
from django_glue.utils import get_request_body_data


@require_http_methods(['POST'])
def action_view(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.content_type != 'application/json':
        return HttpResponse(
            f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain'
        )

    try:
        data = get_request_body_data(request)
    except ValueError:
        return HttpResponse(
            'Invalid JSON',
            status=400,
            content_type='text/plain'
        )

    action_data = dto.GlueActionRequestData(**data)
    proxy = GlueSession(request).get_proxy_by_unique_name(action_data.unique_name)

    action_output = proxy.process_action(action_data)

    if settings.DEBUG:
        print(f'Glue Action Request:\n - Action request data: {action_data.model_dump()}\n - Action output: {action_output}')

    return JsonResponse(action_output, safe=False)


def keep_live_view(request: HttpRequest) -> JsonResponse:
    glue_session = GlueSession(request)
    unique_names = get_request_body_data(request, 'unique_names')

    if len(unique_names) > 0:
        glue_session.renew_proxies(unique_names)

    return JsonResponse(
        data=glue_session.proxy_registry
    )


@require_http_methods(['GET'])
def session_data_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        data=GlueSession(request).proxy_registry,
    )


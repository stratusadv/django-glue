from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse, QueryDict
from django.urls import resolve, reverse
from django.views.decorators.http import require_http_methods

from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE
from django_glue.session import GlueSession
from django_glue import data_transfer_objects as dto, BaseGlueProxy
from django_glue.utils import get_request_body_data


@require_http_methods(['POST'])
def action_view(request: HttpRequest, unique_name: str, action: str) -> JsonResponse | HttpResponse:
    if request.content_type != 'application/json':
        return HttpResponse(
            f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain'
        )

    data = get_request_body_data(request)
    action_data = dto.GlueActionRequestData(**data)

    proxy_access = GlueSession(request).get_proxy_access(unique_name)

    proxy = SUBJECT_TYPE_TO_PROXY_TYPE[
        action_data.context_data['subject_type']].from_action_request_data(
        access=proxy_access,
        unique_name=unique_name,
        **action_data.context_data
    )

    action_response_data = proxy.process_action(action, action_data)

    return JsonResponse(action_response_data, safe=False)


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


@require_http_methods(['GET'])
def view_view(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.content_type != 'application/json':
        return HttpResponse(
            f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain'
        )

    data = get_request_body_data(request)

    view_func = resolve(reverse(data.view_name, kwargs=data.view_kwargs)).func

    view_response: HttpResponse = view_func(request, **data.view_kwargs)

    if hasattr(view_response, 'render') and callable(view_response.render):
        view_response.render()

    response_data = {
        "content": view_response.content.decode('utf-8'),
        "status_code": view_response.status_code,
        "content_type": view_response['Content-Type'],
        # Optional: Capture specific headers, avoiding hop-by-hop ones
        "headers": {k: v for k, v in view_response.items() if
                    k not in ['Content-Length']},
    }

    if hasattr(request, '__glue_context_data__'):
        response_data['glue_context_data'] = request.__glue_context_data__

    return JsonResponse(response_data)

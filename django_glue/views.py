import json
from urllib.parse import urlparse, parse_qs

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.template.response import TemplateResponse
from django.urls import reverse, resolve
from django.views.decorators.http import require_http_methods

from django_glue.encoders import GlueActionDataJSONEncoder
from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE
from django_glue.session import GlueSession
from django_glue import data_transfer_objects as dto
from django_glue.utils import get_request_body_data


class WrappedHttpRequest:
    """Wraps an HttpRequest, overriding select attributes for a target view call."""

    def __init__(self, base_request: HttpRequest, method: str, url_path: str, view_payload: dict):
        self._base = base_request
        self.method = method
        self.body = json.dumps(view_payload).encode('utf-8')
        self.content_type = 'application/json'

        parsed = urlparse(url_path)
        self.path_info = parsed.path

        query_params = parse_qs(parsed.query, keep_blank_values=True)
        query_dict = {}
        for key, values in query_params.items():
            query_dict[key] = values[0] if len(values) == 1 else values
        self.GET = QueryDict(mutable=True)
        for key, value in query_dict.items():
            self.GET[key] = value

    def __getattr__(self, name):
        return getattr(self._base, name)


@require_http_methods(['POST'])
def action_view(request: HttpRequest, unique_name: str, action: str) -> JsonResponse | HttpResponse:
    if request.content_type not in ['application/json', 'multipart/form-data']:
        return HttpResponse(
            f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain'
        )

    action_data = dto.GlueActionRequestData.from_request(request)

    proxy_access = GlueSession(request).get_proxy_access(unique_name)

    proxy = SUBJECT_TYPE_TO_PROXY_TYPE[
        action_data.context_data['subject_type']].from_action_request_data(
        access=proxy_access,
        unique_name=unique_name,
        **action_data.context_data
    )

    action_response_data = proxy.process_action(action, action_data)

    return JsonResponse(action_response_data, safe=False, encoder=GlueActionDataJSONEncoder)


@require_http_methods(['POST'])
def glue_view_view(request: HttpRequest) -> JsonResponse:
    body_data = get_request_body_data(request)

    url_name = body_data.get('url_name', None)
    if url_name:
        try:
            url_path = reverse(url_name)
        except Exception:
            return JsonResponse(
                {'error': f'Could not resolve URL name: {url_name}'},
                status=404
            )
    else:
        url_path = body_data.get('url_path', None)

    if not url_path:
        return JsonResponse(
            {'error': 'Missing url_name or url_path in request body'},
            status=400
        )

    method = body_data.get('method', 'POST')
    view_payload = body_data.get('view_payload', {})

    max_redirects = 5

    for _ in range(max_redirects):
        parsed = urlparse(url_path)
        resolve_path = parsed.path

        try:
            resolved = resolve(resolve_path)
        except Exception:
            return JsonResponse(
                {'error': f'No view found for URL path: {url_path}'},
                status=404
            )

        view_func = resolved.func
        view_kwargs = resolved.kwargs
        wrapped = WrappedHttpRequest(request, method, url_path, view_payload)

        try:
            response = view_func(wrapped, **view_kwargs)
        except Exception as e:
            return JsonResponse(
                {'error': f'View raised an exception: {str(e)}'},
                status=500
            )

        if isinstance(response, HttpResponseRedirect):
            redirect_url = response.url
            if redirect_url.startswith('/'):
                try:
                    resolved_redirect = resolve(redirect_url)
                    url_name = resolved_redirect.view_name
                    url_path = reverse(url_name)
                except Exception:
                    return JsonResponse(
                        {'error': f'Could not resolve redirect URL: {redirect_url}'},
                        status=404
                    )
            else:
                return JsonResponse(
                    {'error': f'External redirect not supported: {redirect_url}'},
                    status=400
                )
            continue

        if isinstance(response, TemplateResponse):
            response.render()

            return JsonResponse({
                'html': response.content.decode('utf-8'),
                'proxy_context_data': getattr(wrapped, '__glue_context_data__', {}),
                'proxy_registry_data': GlueSession(request).proxy_registry
            }, safe=False, encoder=GlueActionDataJSONEncoder)

        elif isinstance(response, HttpResponse):
            return JsonResponse({
                'html': response.content.decode('utf-8'),
                'proxy_context_data': getattr(wrapped, '__glue_context_data__', {}),
                'proxy_registry_data': GlueSession(request).proxy_registry
            })



        return JsonResponse(
            {'error': f'Unsupported response type: {type(response).__name__}'},
            status=500
        )

    return JsonResponse(
        {'error': f'Too many redirects (max {max_redirects})'},
        status=500
    )



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

import logging
from urllib.parse import urlparse

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, resolve
from django.views.decorators.http import require_http_methods

from django_glue.encoders import GlueActionDataJSONEncoder
from django_glue.resolver.view.request import GlueViewHttpRequest
from django_glue.session import GlueSession
from django_glue.utils import get_request_body_data


@require_http_methods(['POST'])
def glue_view_view(request: HttpRequest) -> JsonResponse:
    body_data = get_request_body_data(request)

    url_name = body_data.get('url_name', None)
    if url_name:
        try:
            url_path = reverse(url_name)
        except Exception:
            return JsonResponse({'error': f'Could not resolve URL name: {url_name}'}, status=404)
    else:
        url_path = body_data.get('url_path', None)

    if not url_path:
        return JsonResponse({'error': 'Missing url_name or url_path in request body'}, status=400)

    method = body_data.get('method', 'POST')
    view_payload = body_data.get('view_payload', {})

    max_redirects = 5

    for _ in range(max_redirects):
        parsed = urlparse(url_path)
        resolve_path = parsed.path

        try:
            resolved = resolve(resolve_path)
        except Exception:
            return JsonResponse({'error': f'No view found for URL path: {url_path}'}, status=404)

        view_func = resolved.func
        view_kwargs = resolved.kwargs
        wrapped = GlueViewHttpRequest(request, method, url_path, view_payload)

        try:
            response = view_func(wrapped, **view_kwargs)
        except Exception as e:
            logging.exception(e)
            return JsonResponse({'error': f'View raised an exception: {e!s}'}, status=500)

        if isinstance(response, HttpResponseRedirect):
            redirect_url = response.url
            if redirect_url.startswith('/'):
                try:
                    resolved_redirect = resolve(redirect_url)
                    url_name = resolved_redirect.view_name
                    url_path = reverse(url_name)
                except Exception:
                    return JsonResponse(
                        {'error': f'Could not resolve redirect URL: {redirect_url}'}, status=404
                    )
            else:
                return JsonResponse(
                    {'error': f'External redirect not supported: {redirect_url}'}, status=400
                )
            continue

        if isinstance(response, TemplateResponse):
            response.render()

            return JsonResponse(
                {
                    'html': response.content.decode('utf-8'),
                    'proxy_context_data': getattr(wrapped, '__glue_context_data__', {}),
                    'proxy_registry_data': GlueSession(request).proxy_registry,
                },
                safe=False,
                encoder=GlueActionDataJSONEncoder,
            )

        if isinstance(response, HttpResponse):
            return JsonResponse(
                {
                    'html': response.content.decode('utf-8'),
                    'proxy_context_data': getattr(wrapped, '__glue_context_data__', {}),
                    'proxy_registry_data': GlueSession(request).proxy_registry,
                }
            )

        return JsonResponse(
            {'error': f'Unsupported response type: {type(response).__name__}'}, status=500
        )

    return JsonResponse({'error': f'Too many redirects (max {max_redirects})'}, status=500)

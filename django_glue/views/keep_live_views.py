from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods

from django_glue.session import GlueSession
from django_glue.utils import get_request_body_data



@require_http_methods(['POST'])
def keep_live_view(request: HttpRequest) -> JsonResponse:
    glue_session = GlueSession(request)
    unique_names = get_request_body_data(request=request, key='unique_names')

    if len(unique_names) > 0:
        glue_session.renew_proxies(unique_names)

    return JsonResponse(data=glue_session.proxy_registry)


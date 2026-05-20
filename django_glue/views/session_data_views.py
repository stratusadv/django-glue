from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.session import GlueSession


@require_http_methods(['GET'])
def session_data_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse(data=GlueSession(request).proxy_registry)

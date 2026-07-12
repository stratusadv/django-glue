from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods

from django_glue.resolver.view.resolver import ViewResolver


@require_http_methods(['POST'])
def glue_view_view(request: HttpRequest) -> JsonResponse:
    return ViewResolver(request).resolve()

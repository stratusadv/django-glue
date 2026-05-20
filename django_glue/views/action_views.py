from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.resolver.action.resolver import ActionResolver


@require_http_methods(['POST'])
def action_view(request: HttpRequest, unique_name: str, action: str) -> JsonResponse | HttpResponse:
    return ActionResolver(request=request, action=action, unique_name=unique_name).resolve()

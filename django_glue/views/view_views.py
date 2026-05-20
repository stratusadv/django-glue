from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_http_methods

from django_glue.resolver.view.resolver import GlueViewResolver


@require_http_methods(['POST'])
def glue_view_view(request: HttpRequest) -> JsonResponse:
    return GlueViewResolver(request).resolve()

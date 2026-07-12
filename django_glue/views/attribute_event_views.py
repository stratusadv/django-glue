from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from django.conf import settings
from django_glue.exceptions import GlueAccessError, GlueInvalidPolicyError
from django_glue.resolver.attribute_event.resolver import ProxyBoundAttributeEventResolver
from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent


@require_http_methods(['POST'])
# Including variadic kwargs here purely for the purpose
# of showing proxy_name and bound_attribute_name in logs
def proxy_bound_attribute_event_view(request: HttpRequest, *, proxy_name: str, attribute_name: str) -> JsonResponse | HttpResponse:
    try:
        event = BoundProxyAttributeEvent.model_validate(request)
    except (GlueAccessError, GlueInvalidPolicyError) as e:
        return HttpResponse(
            content=str(e),
            status=403,
            content_type='text/plain',
        )
    except ValidationError as e:
        if 'Insufficient access' in str(e):
            return HttpResponse(
                content=str(e),
                status=403,
                content_type='text/plain',
            )
        return HttpResponse(
            content=f'{e}' if settings.DEBUG else 'Malformed Glue Proxy Event',
            status=400,
            content_type='text/plain',
        )

    try:
        return ProxyBoundAttributeEventResolver(event).resolve()
    except (GlueAccessError, GlueInvalidPolicyError) as e:
        return HttpResponse(
            content=str(e),
            status=403,
            content_type='text/plain',
        )

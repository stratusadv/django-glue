import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from django_glue.exceptions import GlueError, GlueRequestError
from django_glue.resolver.attribute_event.resolver import ProxyBoundAttributeEventResolver
from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent

logger = logging.getLogger('django.request')


def _error_response(error: GlueError) -> JsonResponse:
    is_server_error = error.status >= 500
    expose_details = settings.DEBUG or not is_server_error

    return JsonResponse(
        {
            'error': {
                'code': error.code,
                'message': str(error) if expose_details else 'An unexpected Glue server error occurred.',
                'status': error.status,
                'details': error.details() if expose_details else {},
            }
        },
        status=error.status,
    )


@require_POST
def proxy_bound_attribute_event_view(
    request: HttpRequest,
    *,
    proxy_name: str,
    attribute_name: str
) -> JsonResponse:
    try:
        event = BoundProxyAttributeEvent.model_validate(request)
    except GlueError as e:
        if e.status >= 500:
            logger.exception(
                "Django Glue bound attribute event failed while validating request: proxy=%s attribute=%s",
                proxy_name,
                attribute_name,
            )
        return _error_response(e)
    except ValidationError as e:
        message = f'{e}' if settings.DEBUG else 'Malformed Glue Proxy Event'
        return _error_response(
            GlueRequestError(
                code='malformed_event',
                message=message,
                details={'errors': e.errors(include_input=False)} if settings.DEBUG else {},
            )
        )

    try:
        return ProxyBoundAttributeEventResolver(event).resolve()
    except GlueError as e:
        if e.status >= 500:
            logger.exception(
                "Django Glue bound attribute event failed: proxy=%s attribute=%s",
                proxy_name,
                attribute_name,
            )
        return _error_response(e)

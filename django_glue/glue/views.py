from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from django_glue.glue.schemas import AttributeCallResolverContext
from django_glue.exceptions import GlueError, GlueRequestError
from django_glue.resolver.callable_attribute import AttributeCallResolver
from django_glue.views.error_response import glue_error_response

logger = logging.getLogger('django.request')


@require_POST
def glue_attribute_call_view(request: HttpRequest, *, object_name: str, attribute_name: str) -> JsonResponse:
    try:
        attribute_request = AttributeCallResolverContext.model_validate(request)
    except GlueError as e:
        if e.status >= 500:
            logger.exception(
                'Django Glue attribute request failed while validating request: object=%s',
                object_name,
            )
        return glue_error_response(e)
    except ValidationError as e:
        message = f'{e}' if settings.DEBUG else 'Malformed Glue Attribute Request'
        return glue_error_response(
            GlueRequestError(
                code='malformed_attribute_request',
                message=message,
                details={'errors': e.errors(include_input=False)} if settings.DEBUG else {},
            )
        )

    try:
        return AttributeCallResolver(attribute_request).resolve()
    except GlueError as e:
        if e.status >= 500:
            logger.exception('Django Glue attribute request failed: object=%s', object_name)
        return glue_error_response(e)

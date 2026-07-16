from django.conf import settings
from django.http import JsonResponse

from django_glue.exceptions import GlueError


def glue_error_response(error: GlueError) -> JsonResponse:
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

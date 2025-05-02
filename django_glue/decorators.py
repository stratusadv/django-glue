from __future__ import annotations
from django.http import HttpResponse
from django.http import JsonResponse
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest

def require_content_types(*content_types) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        def _wrapped_view(request: WSGIRequest, *args, **kwargs) -> Any:
            if request.content_type not in content_types:
                return JsonResponse({'error': 'Unsupported Media Type'}, status=415)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def require_query_method(view_func: Callable) -> Callable:
    def _wrapped_view(request: WSGIRequest, *args, **kwargs) -> Any:
        if request.method != 'QUERY':
            return HttpResponse('Method Not Allowed', status=405)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

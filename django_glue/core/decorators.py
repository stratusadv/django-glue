from django.http import JsonResponse
from django.http import HttpResponse


def require_content_types(*content_types):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.content_type not in content_types:
                return JsonResponse({'error': 'Unsupported Media Type'}, status=415)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def require_query_method(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.method != 'QUERY':
            return HttpResponse('Method Not Allowed', status=405)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

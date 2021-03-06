import logging

from django.urls import resolve


class GlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        current_url = resolve(request.path_info).url_name
        if current_url != 'django_glue_handler':
            request.session['django_glue'] = dict()

        return None

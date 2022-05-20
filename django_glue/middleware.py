from django.http import Http404
from django.shortcuts import render


class GlueMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'grouping_slug' in view_kwargs and request.user.is_authenticated:
            from django_glue import models
            try:
                pass
            except:
                pass

        return None
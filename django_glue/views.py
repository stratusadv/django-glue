import logging

from django_glue.handlers import GlueRequestHandler


def glue_ajax_handler_view(request):
    return GlueRequestHandler(request).process_response()


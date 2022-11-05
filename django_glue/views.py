import logging

from django_glue.handlers import GlueDataRequestHandler


def glue_ajax_handler_view(request):
    return GlueDataRequestHandler(request).process_response()


import json

from django.shortcuts import HttpResponse

from django_glue.handlers import GlueDataRequestHandler
from django_glue.sessions import GlueKeepLiveSession


def glue_data_ajax_handler_view(request):
    return GlueDataRequestHandler(request).process_response()


def glue_keep_live_handler_view(request):
    data = json.loads(request.body.decode('utf-8'))
    unique_names = data['unique_names']

    GlueKeepLiveSession(request).update_unique_names(unique_names)

    return HttpResponse(status=204)

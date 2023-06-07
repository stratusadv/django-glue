from django.shortcuts import HttpResponse

from django_glue.handlers import GlueDataRequestHandler
from django_glue.sessions import GlueKeepLiveSession


def glue_data_ajax_handler_view(request):
    return GlueDataRequestHandler(request).process_response()


def glue_keep_live_handler_view(request):
    keep_live_url_path = request.GET.get('keep_live_url_path', None)
    if keep_live_url_path:
        GlueKeepLiveSession(request).update_url_path(keep_live_url_path)
    return HttpResponse(status=204)

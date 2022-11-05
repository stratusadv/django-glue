from django.shortcuts import HttpResponse

from django_glue.handlers import GlueDataRequestHandler
from django_glue.glue import update_glue_keep_live

def glue_data_ajax_handler_view(request):
    return GlueDataRequestHandler(request).process_response()

def glue_keep_live_handler_view(request):
    keep_live_path = request.GET.get('keep_live_path', None)
    if keep_live_path:
        update_glue_keep_live(request, keep_live_path)
    return HttpResponse(status=204)
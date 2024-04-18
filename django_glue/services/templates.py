from django_glue.handler.data import GlueBodyData
from django_glue.services.services import Service
from django.shortcuts import HttpResponse
from django.template.loader import render_to_string

from django_glue.session.data import GlueMetaData


class GlueTemplateService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data

    def process_get_action(self, body_data: GlueBodyData) -> HttpResponse:
        return HttpResponse(render_to_string(self.meta_data.template, body_data.data['data']))

import logging

from django_glue.data_classes import GlueBodyData, GlueMetaData
from django_glue.services.services import Service
from django.shortcuts import HttpResponse
from django.template.loader import render_to_string


class GlueTemplateService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data

    def process_get_action(self, body_data: GlueBodyData) -> HttpResponse:
        return HttpResponse(render_to_string(self.meta_data.template, body_data.data['data']))

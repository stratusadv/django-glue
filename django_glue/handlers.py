import logging, json

from django.contrib.contenttypes.models import ContentType
from django.forms import model_to_dict
from django.http import Http404

from django_glue.responses import generate_json_response, generate_json_404_response
from django_glue.sessions import GlueSession
from django_glue.types import GlueContextData, GlueMetaData
from django_glue.enums import GlueConnection, GlueAccess
from django_glue.utils import process_and_save_field_value, process_and_save_form_values, decode_query_set_from_str, \
    generate_simple_field_dict
from django_glue.conf import settings


class GlueDataRequestHandler:
    def __init__(self, request):
        self.request = request

        if request.content_type == 'application/json':
            logging.warning(request.body.decode('utf-8'))
            self.body_data = json.loads(request.body.decode('utf-8'))
        else:
            raise Http404

        self.unique_name = self.body_data['unique_name']

        self.glue_session = GlueSession(request)
        self.context = self.glue_session['context']

        if self.unique_name in self.context:
            self.method = request.method

            self.meta_data: GlueMetaData = GlueMetaData(
                **self.glue_session['meta'][self.unique_name]
            )

            self.connection = GlueConnection(self.context[self.unique_name]['connection']),
            self.access = GlueAccess(self.context[self.unique_name]['access'])

            self.model_class = self.meta_data.model_class

            if self.connection == GlueConnection.MODEL_OBJECT:
                try:
                    self.model_object = self.model_class.objects.get(pk=self.meta_data.object_pk)
                except self.model_class.DoesNotExist:
                    self.model_object = None

            elif self.connection == GlueConnection.QUERY_SET:
                self.query_set = decode_query_set_from_str(self.meta_data.query_set_str)

        else:
            raise Http404

    def process_response(self):
        if self.method == 'QUERY':
            if self.connection == GlueConnection.MODEL_OBJECT:
                pass
            elif self.connection == GlueConnection.QUERY_SET:
                pass
            else:
                return generate_json_404_response()
        else:
            return generate_json_404_response()


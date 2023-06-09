import logging, json

from django_glue.services import GlueModelObjectService, GlueQuerySetService
from django_glue.responses import generate_json_response, generate_json_404_response
from django_glue.sessions import GlueSession
from django_glue.data_classes import GlueMetaData, GlueBodyData
from django_glue.enums import GlueConnection, GlueAccess
from django_glue.utils import decode_query_set_from_str


class GlueDataRequestHandler:
    def __init__(self, request):
        self.request = request

        self.is_valid_request = True

        if request.content_type == 'application/json':
            logging.warning(request.body.decode('utf-8'))
            self.body_data = GlueBodyData(request.body)
        else:
            self.is_valid_request = False

        self.unique_name = self.body_data['unique_name']

        self.glue_session = GlueSession(request)
        self.context = self.glue_session['context']

        if self.unique_name in self.context:
            self.method = request.method

            self.meta_data: GlueMetaData = GlueMetaData(
                **self.glue_session['meta'][self.unique_name]
            )

            self.connection = GlueConnection(self.context[self.unique_name]['connection'])

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
            self.is_valid_request = False

    def process_response(self):
        if self.method == 'QUERY' and self.is_valid_request:

            if self.connection == GlueConnection.MODEL_OBJECT:
                try:
                    glue_model_object_service = GlueModelObjectService(
                        self.meta_data.app_label,
                        self.meta_data.model,
                        self.meta_data.object_pk,
                    )

                    json_response_data = glue_model_object_service.process_body_data(self.access, self.body_data)

                    return json_response_data.to_django_json_response()

                except:
                    return generate_json_404_response()

            elif self.connection == GlueConnection.QUERY_SET:
                try:
                    glue_query_set_service = GlueQuerySetService(
                        self.meta_data.app_label,
                        self.meta_data.model,
                        self.meta_data.query_set_str,
                    )

                    json_response_data = glue_query_set_service.process_body_data(self.access, self.body_data)

                    return json_response_data.to_django_json_response()

                except:
                    return generate_json_404_response()

            else:
                return generate_json_404_response()

        else:
            return generate_json_404_response()


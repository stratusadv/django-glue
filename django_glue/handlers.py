import logging, json

from django_glue.services import GlueModelObjectService, GlueQuerySetService
from django_glue.responses import generate_json_404_response
from django_glue.sessions import GlueSession
from django_glue.data_classes import GlueMetaData, GlueBodyData
from django_glue.enums import GlueConnection, GlueAccess


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

        else:
            self.is_valid_request = False

        logging.warning(f'{self.is_valid_request = }')

    def process_response(self):
        if self.method == 'QUERY' and self.is_valid_request:
            if self.connection == GlueConnection.MODEL_OBJECT:
                glue_model_object_service = GlueModelObjectService(
                    self.meta_data,
                )

                json_response_data = glue_model_object_service.process_body_data(self.access, self.body_data)
                return json_response_data.to_django_json_response()

            elif self.connection == GlueConnection.QUERY_SET:
                glue_query_set_service = GlueQuerySetService(
                    self.meta_data,
                )

                json_response_data = glue_query_set_service.process_body_data(self.access, self.body_data)
                return json_response_data.to_django_json_response()

            else:
                return generate_json_404_response()

        else:
            return generate_json_404_response()

from abc import ABC

from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.factories import glue_model_object_from_glue_query_set_session
from django_glue.entities.query_set.actions import GlueQuerySetAction
from django_glue.entities.query_set.entities import GlueQuerySet
from django_glue.entities.query_set.factories import decode_query_set_from_str
from django_glue.entities.query_set.responses import GlueQuerySetJsonData
from django_glue.entities.query_set.sessions import GlueQuerySetSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GlueQuerySetHandler(GlueRequestHandler, ABC):
    _session_data_class = GlueQuerySetSessionData
    _action_class = GlueQuerySetAction

    def initialize_glue_entity(self) -> GlueEntity:
        return GlueQuerySet(
            unique_name=self.session_data.unique_name,
            query_set=decode_query_set_from_str(self.session_data.query_set_str),
            access=self.session_data.access,
            connection=self.session_data.connection,
            included_fields=self.session_data.included_fields,
            excluded_fields=self.session_data.excluded_fields,
            included_methods=self.session_data.included_methods,
        )


class AllGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        response_data = GlueQuerySetJsonData()

        for model_object in self.glue_entity.query_set.all():
            glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)
            response_data.model_objects.append(glue_model_object.to_object_json_data())

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=response_data.to_dict()
        )


class FilterGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        response_data = GlueQuerySetJsonData()

        for model_object in self.glue_entity.query_set.filter(**self.glue_body_data.data['data']['filter_params']):
            glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)
            response_data.model_objects.append(glue_model_object.to_object_json_data())

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=response_data.to_dict()
        )


class GetGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        response_data = GlueQuerySetJsonData()

        model_object = self.glue_entity.query_set.get(id=self.glue_body_data.data['data']['id'])
        glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)
        response_data.model_objects.append(glue_model_object.to_object_json_data())

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=response_data.to_dict()
        )


class UpdateGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Updates and returns a list of model objects

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=self.glue_entity.generate_field_data()
        )


class DeleteGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Deletes the query set
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted model object!',
        )


class MethodGlueQuerySetHandler(GlueQuerySetHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Do we call this on they query set or each model object?
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
        )

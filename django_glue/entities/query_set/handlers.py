from django_glue.entities.model_object.factories import glue_model_object_from_glue_query_set_session, \
    glue_model_objects_from_query_set
from django_glue.entities.query_set.actions import GlueQuerySetAction
from django_glue.entities.query_set.factories import glue_query_set_from_session_data
from django_glue.entities.query_set.post_data import FilterGlueQuerySetPostData, GetGlueQuerySetPostData, \
    DeleteGlueQuerySetPostData

from django_glue.entities.query_set.sessions import GlueQuerySetSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class AllGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.ALL
    _session_data_class = GlueQuerySetSessionData

    def process_response(self) -> GlueJsonResponseData:

        glue_query_set = glue_query_set_from_session_data(self.session_data)
        glue_model_objects = glue_model_objects_from_query_set(glue_query_set.query_set.all(), self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_query_set.to_response_data(glue_model_objects)
        )


class DeleteGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.DELETE
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = DeleteGlueQuerySetPostData

    def process_response(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)

        filtered_query_set = glue_query_set.query_set.filter(id__in=self.post_data.id)
        filtered_query_set.delete()

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted queryset!',
        )


class FilterGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.FILTER
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = FilterGlueQuerySetPostData

    def process_response(self) -> GlueJsonResponseData:

        glue_query_set = glue_query_set_from_session_data(self.session_data)
        filtered_query_set = glue_query_set.query_set.filter(**self.post_data.filter_params)
        glue_model_objects = glue_model_objects_from_query_set(filtered_query_set, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_query_set.to_response_data(glue_model_objects)
        )


class GetGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.ALL
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = GetGlueQuerySetPostData

    def process_response(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)

        model_object = glue_query_set.query_set.get(id=self.post_data.id)
        glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=glue_query_set.to_response_data([glue_model_object])
        )


class UpdateGlueQuerySetHandler(GlueRequestHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Updates and returns a list of model objects

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=self.glue_entity.generate_field_data()
        )


class MethodGlueQuerySetHandler(GlueRequestHandler):
    def process_response(self) -> GlueJsonResponseData:
        # Todo: Do we call this on they query set or each model object?
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
        )

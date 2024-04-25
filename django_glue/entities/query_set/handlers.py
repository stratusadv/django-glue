from django_glue.access.decorators import check_access
from django_glue.entities.model_object.factories import glue_model_object_from_glue_query_set_session, \
    glue_model_objects_from_query_set
from django_glue.entities.model_object.response_data import GlueModelObjectJsonData, MethodGlueModelObjectJsonData
from django_glue.entities.query_set.actions import GlueQuerySetAction
from django_glue.entities.query_set.factories import glue_query_set_from_session_data
from django_glue.entities.post_data import GetPostData, DeletePostData, UpdatePostData, MethodPostData
from django_glue.entities.query_set.post_data import FilterGlueQuerySetPostData
from django_glue.entities.query_set.response_data import GlueQuerySetJsonData, MethodGlueQuerySetJsonData

from django_glue.entities.query_set.session_data import GlueQuerySetSessionData
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class AllGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.ALL
    _session_data_class = GlueQuerySetSessionData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:

        glue_query_set = glue_query_set_from_session_data(self.session_data)
        glue_model_objects = glue_model_objects_from_query_set(glue_query_set.query_set.all(), self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueQuerySetJsonData([GlueModelObjectJsonData(glue_model_object.fields) for glue_model_object in glue_model_objects])
        )


class DeleteGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.DELETE
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = DeletePostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
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

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:

        glue_query_set = glue_query_set_from_session_data(self.session_data)
        filtered_query_set = glue_query_set.query_set.filter(**self.post_data.filter_params)
        glue_model_objects = glue_model_objects_from_query_set(filtered_query_set, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueQuerySetJsonData([GlueModelObjectJsonData(glue_model_object.fields) for glue_model_object in glue_model_objects])
        )


class GetGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.GET
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = GetPostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)

        model_object = glue_query_set.query_set.get(id=self.post_data.id)
        glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueQuerySetJsonData([GlueModelObjectJsonData(glue_model_object.fields)])
        )


class NullObjectGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.NULL_OBJECT
    _session_data_class = GlueQuerySetSessionData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)
        glue_model_object = glue_model_object_from_glue_query_set_session(glue_query_set.model(), self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueQuerySetJsonData([GlueModelObjectJsonData(glue_model_object.fields)])
        )


class UpdateGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.UPDATE
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = UpdatePostData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)

        model_object = glue_query_set.query_set.get(id=self.post_data.id)

        glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)
        glue_model_object.update(self.post_data.fields)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=GlueQuerySetJsonData([GlueModelObjectJsonData(glue_model_object.fields)])
        )


class MethodGlueQuerySetHandler(GlueRequestHandler):
    action = GlueQuerySetAction.METHOD
    _session_data_class = GlueQuerySetSessionData
    _post_data_class = MethodPostData

    def process_response_data(self) -> GlueJsonResponseData:
        glue_query_set = glue_query_set_from_session_data(self.session_data)
        filtered_query_set = glue_query_set.query_set.filter(id__in=self.post_data.id)

        method_return_data = []

        for model_object in filtered_query_set:
            glue_model_object = glue_model_object_from_glue_query_set_session(model_object, self.session_data)
            method_return = glue_model_object.call_method(self.post_data.method, self.post_data.kwargs)
            method_return_data.append(MethodGlueModelObjectJsonData(method_return))

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=MethodGlueQuerySetJsonData(method_return_data)
        )

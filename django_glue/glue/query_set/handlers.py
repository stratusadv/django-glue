from django_glue.access.decorators import check_access
from django_glue.glue.model_object.response_data import ModelObjectGlueJsonData, MethodModelObjectGlueJsonData
from django_glue.glue.model_object.tools import model_object_glue_from_query_set_glue_session_data, \
    model_object_glues_from_query_set_glue_and_session_data
from django_glue.glue.post_data import GetPostData, DeletePostData, UpdatePostData, MethodPostData
from django_glue.glue.query_set.actions import QuerySetGlueActionType
from django_glue.glue.query_set.post_data import FilterQuerySetGluePostData
from django_glue.glue.query_set.response_data import QuerySetGlueJsonData, MethodQuerySetGlueJsonData, \
    ToChoicesQuerySetGlueJsonData
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData
from django_glue.glue.query_set.tools import query_set_glue_from_session_data
from django_glue.handler.handlers import GlueRequestProcessor
from django_glue.response.data import JsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class AllQuerySetGlueHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.ALL
    _session_data_class = QuerySetGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:

        query_set_glue = query_set_glue_from_session_data(self.session_data)
        glue_model_objects = model_object_glues_from_query_set_glue_and_session_data(query_set_glue.query_set.all(), self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(glue_model_object.fields) for glue_model_object in glue_model_objects])
        )


class DeleteGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.DELETE
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = DeletePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)

        filtered_query_set = query_set_glue.query_set.filter(id__in=self.post_data.id)
        filtered_query_set.delete()

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted queryset!',
        )


class FilterGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.FILTER
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = FilterQuerySetGluePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:

        query_set_glue = query_set_glue_from_session_data(self.session_data)
        filtered_query_set = query_set_glue.query_set.filter(**self.post_data.filter_params)
        model_objects_glue = model_object_glues_from_query_set_glue_and_session_data(filtered_query_set, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(glue_model_object.fields) for glue_model_object in model_objects_glue])
        )


class GetGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.GET
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = GetPostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)

        model_object = query_set_glue.query_set.get(id=self.post_data.id)
        model_object_glue = model_object_glue_from_query_set_glue_session_data(model_object, self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class NullObjectGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.NULL_OBJECT
    _session_data_class = QuerySetGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)
        model_object_glue = model_object_glue_from_query_set_glue_session_data(query_set_glue.model(), self.session_data)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class MethodGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.METHOD
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = MethodPostData

    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)

        if isinstance(self.post_data.id, int):
            # Called from a glue queryset on a model object
            model_object = query_set_glue.query_set.get(id=self.post_data.id)
            model_object_glue = model_object_glue_from_query_set_glue_session_data(model_object, self.session_data)
            method_return = model_object_glue.call_method(self.post_data.method, self.post_data.kwargs)

            return generate_json_200_response_data(
                message_title='Success',
                message_body='Successfully updated model object!',
                data=MethodModelObjectGlueJsonData(method_return)
            )
        else:
            # Called from a glue queryset
            filtered_query_set = query_set_glue.query_set.filter(id__in=self.post_data.id)

            method_return_data = []

            for model_object in filtered_query_set:
                model_object_glue = model_object_glue_from_query_set_glue_session_data(model_object, self.session_data)
                method_return = model_object_glue.call_method(self.post_data.method, self.post_data.kwargs)
                method_return_data.append(MethodModelObjectGlueJsonData(method_return))

            return generate_json_200_response_data(
                message_title='Success',
                message_body='Successfully updated model object!',
                data=MethodQuerySetGlueJsonData(method_return_data)
            )


class UpdateGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.UPDATE
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = UpdatePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)

        model_object = query_set_glue.query_set.get(id=self.post_data.id)

        model_object_glue = model_object_glue_from_query_set_glue_session_data(model_object, self.session_data)
        model_object_glue.update(self.post_data.fields)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class ToChoicesGlueQuerySetHandler(GlueRequestProcessor):
    action = QuerySetGlueActionType.TO_CHOICES
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = FilterQuerySetGluePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = query_set_glue_from_session_data(self.session_data)
        filtered_query_set = query_set_glue.query_set.filter(**self.post_data.filter_params)
        model_object_glues = model_object_glues_from_query_set_glue_and_session_data(filtered_query_set, self.session_data)
        choices = [(model_object_glue.model_object.pk, str(model_object_glue.model_object)) for model_object_glue in model_object_glues]

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=ToChoicesQuerySetGlueJsonData(choices)
        )

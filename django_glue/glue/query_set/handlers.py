from django_glue.access.decorators import check_access
from django_glue.glue.model_object.response_data import ModelObjectGlueJsonData, MethodModelObjectGlueJsonData
from django_glue.glue.post_data import GetPostData, DeletePostData, UpdatePostData, MethodPostData
from django_glue.glue.query_set.actions import QuerySetGlueAction
from django_glue.glue.query_set.glue import QuerySetGlue
from django_glue.glue.query_set.post_data import FilterQuerySetGluePostData
from django_glue.glue.query_set.response_data import QuerySetGlueJsonData, MethodQuerySetGlueJsonData, \
    ToChoicesQuerySetGlueJsonData
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData
from django_glue.handler.handlers import BaseRequestHandler
from django_glue.response.data import JsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class AllQuerySetGlueHandler(BaseRequestHandler):
    action = QuerySetGlueAction.ALL
    _session_data_class = QuerySetGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()
        glue_model_objects = self.session_data.extract_model_object_glues_matching_queryset(
            query_set_glue.query_set.all()
        )

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(glue_model_object.fields) for glue_model_object in glue_model_objects])
        )


class DeleteGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.DELETE
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = DeletePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()

        filtered_query_set = query_set_glue.query_set.filter(id__in=self.post_data.id)
        filtered_query_set.delete()

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully deleted queryset!',
        )


class FilterGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.FILTER
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = FilterQuerySetGluePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()
        filtered_query_set = query_set_glue.query_set.filter(**self.post_data.filter_params)
        model_objects_glue = self.session_data.extract_model_object_glues_matching_queryset(
            filtered_query_set
        )

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(glue_model_object.fields) for glue_model_object in model_objects_glue])
        )


class GetGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.GET
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = GetPostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()

        model_object = query_set_glue.query_set.get(id=self.post_data.id)
        model_object_glue = self.session_data.extract_model_object_glue_matching_model_object(
            model_object=model_object,
        )

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class NullObjectGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.NULL_OBJECT
    _session_data_class = QuerySetGlueSessionData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()
        model_object_glue = self.session_data.extract_model_object_glue_matching_model_object(
            model_object=query_set_glue.model()
        )

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class MethodGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.METHOD
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = MethodPostData

    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()

        if isinstance(self.post_data.id, int):
            # Called from a glue queryset on a model object
            model_object = query_set_glue.query_set.get(id=self.post_data.id)
            model_object_glue = self.session_data.extract_model_object_glue_matching_model_object(
                model_object=model_object,
            )
            method_return = model_object_glue.call_method(
                self.post_data.method,
                self.post_data.kwargs
            )

            return generate_json_200_response_data(
                message_title='Success',
                message_body='Successfully updated model object!',
                data=MethodModelObjectGlueJsonData(method_return)
            )
        else:
            # Called from a glue queryset
            filtered_query_set = query_set_glue.query_set.filter(id__in=self.post_data.id)


            model_object_glues = self.session_data.extract_model_object_glues_matching_queryset(
                query_set=filtered_query_set
            )

            # @Chase - Would it make more sense to add call_method to query_set_glue?
            # It seems like these implementation details make more sense there
            method_return_data = [
                MethodModelObjectGlueJsonData(
                    model_object_glue.call_method(
                        self.post_data.method,
                        self.post_data.kwargs
                    )
                )
                for model_object_glue in model_object_glues
            ]

            return generate_json_200_response_data(
                message_title='Success',
                message_body='Successfully updated model object!',
                data=MethodQuerySetGlueJsonData(method_return_data)
            )


class UpdateGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.UPDATE
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = UpdatePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()

        model_object = query_set_glue.query_set.get(id=self.post_data.id)

        model_object_glue = self.session_data.extract_model_object_glue_matching_model_object(
            model_object=model_object,
        )
        model_object_glue.update(self.post_data.fields)

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully updated model object!',
            data=QuerySetGlueJsonData([ModelObjectGlueJsonData(model_object_glue.fields)])
        )


class ToChoicesGlueQuerySetHandler(BaseRequestHandler):
    action = QuerySetGlueAction.TO_CHOICES
    _session_data_class = QuerySetGlueSessionData
    _post_data_class = FilterQuerySetGluePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        query_set_glue = self.session_data.to_queryset_glue()
        filtered_query_set = query_set_glue.query_set.filter(**self.post_data.filter_params)


        model_object_glues = self.session_data.extract_model_object_glues_matching_queryset(
            query_set=filtered_query_set
        )

        # Is it necessary to convert to model object glues here?
        # Why can't we just directly iterate over the filtered_query_set?
        # i.e.
        # choices = [
        #     (model_object.pk, str(model_object))
        #     for model_object in filtered_query_set
        # ]

        choices = [
            (model_object_glue.model_object.pk, str(model_object_glue.model_object))
            for model_object_glue in model_object_glues
        ]

        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=ToChoicesQuerySetGlueJsonData(choices)
        )

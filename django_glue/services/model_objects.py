from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.handler.data import GlueBodyData
from django_glue.response.data import GlueJsonResponseData, GlueJsonData
from django_glue.response.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.services.services import Service
from django_glue.session.data import GlueMetaData
from django_glue.utils import generate_simple_field_dict, check_valid_method_kwargs, \
    type_set_method_kwargs, generate_field_dict


class GlueModelObjectService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        self.model_class = None
        self.object: Optional[Model] = None

    def load_object(self):
        self.load_model_class()
        try:
            self.object = self.model_class.objects.get(pk=self.meta_data.object_pk)
        except self.model_class.DoesNotExist:
            self.object = self.model_class()

    def load_model_class(self):
        self.model_class = ContentType.objects.get_by_natural_key(
            self.meta_data.app_label,
            self.meta_data.model
        ).model_class()

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_object()
        json_data = GlueJsonData()

        json_data.simple_fields = generate_simple_field_dict(
            self.object,
            self.meta_data.fields,
            self.meta_data.exclude,
        )

        json_data.fields = generate_field_dict(self.object, self.meta_data.fields, self.meta_data.exclude)

        return generate_json_200_response_data(
            'THE GET ACTION',
            'this is a response from an model object get action!!! stay tuned!',
            json_data,
        )

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_object()

        field_dict = generate_field_dict(self.object, self.meta_data.fields, self.meta_data.exclude)
        for field_name in field_dict.keys():
            self.object.__dict__[field_name] = body_data['data'][field_name]

        self.object.save()

        return generate_json_200_response_data(
            'THE UPDATE ACTION',
            'this is a response from an model object update action!'
        )

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_object()
        self.object.delete()

        return generate_json_200_response_data(
            'THE DELETE ACTION',
            'this is a response from an model object delete action!'
        )

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_object()
        kwargs = body_data['data']['kwargs']
        method_return = None

        if body_data['data']['method'] in self.meta_data.methods and hasattr(self.model_class, body_data['data']['method']):
            method = getattr(self.object, body_data['data']['method'])

            if check_valid_method_kwargs(method, kwargs):
                type_set_kwargs = type_set_method_kwargs(method, kwargs)

                method_return = method(**type_set_kwargs)
            else:
                return generate_json_404_response_data()
        else:
            return generate_json_404_response_data()

        json_data = GlueJsonData()

        json_data.method_return = method_return

        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            json_data
        )



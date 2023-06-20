from typing import Optional

from django.db.models import QuerySet

from django_glue.data_classes import GlueJsonResponseData, GlueBodyData, GlueMetaData, GlueJsonData
from django_glue.responses import generate_json_200_response_data
from django_glue.services.services import Service
from django_glue.utils import decode_query_set_from_str, generate_simple_field_dict, get_fields_from_model


class GlueQuerySetService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        self.query_set: Optional[QuerySet] = None

    def load_query_set(self):
        self.query_set = decode_query_set_from_str(self.meta_data.query_set_str)

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()
        data = []

        if 'filter_params' in body_data['data']:
            for model_object in self.query_set.filter(**body_data['data']['filter_params']):
                data.append(GlueJsonData(simple_fields=generate_simple_field_dict(
                        model_object, self.meta_data.fields, self.meta_data.exclude)))

        elif 'all' in body_data['data']:
            for model_object in self.query_set.all():
                data.append(GlueJsonData(simple_fields=generate_simple_field_dict(
                        model_object, self.meta_data.fields, self.meta_data.exclude)))

        else:
            model_object = self.query_set.get(id=body_data['data']['id'])
            data = GlueJsonData(simple_fields=generate_simple_field_dict(
                model_object, self.meta_data.fields, self.meta_data.exclude))

        return generate_json_200_response_data(
            'THE QUERY GET ACTION',
            'this is a response from an query set get action',
            data
        )

    def process_create_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        model_object = self.meta_data.model_class()

        for field in get_fields_from_model(self.meta_data.model_class):
            if field.name in body_data['data'] and field.name != 'id':
                setattr(model_object, field.name, body_data['data'][field.name])

        model_object.save()

        return generate_json_200_response_data(
            'THE QUERY CREATE ACTION',
            'this is a response from an query set create action!'
        )

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        model_object = self.meta_data.model_class.objects.get(id=body_data['data']['id'])

        for field in get_fields_from_model(self.meta_data.model_class):
            if field.name in body_data['data'] and field.name != 'id':
                model_object.__dict__[field.name] = body_data['data'][field.name]

        model_object.save()

        return generate_json_200_response_data(
            'THE QUERY UPDATE ACTION',
            'this is a response from an query set update action!'
        )

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        model_object = self.query_set.get(id=body_data['data']['id'])
        model_object.delete()

        return generate_json_200_response_data(
            'THE QUERY DELETE ACTION',
            'this is a response from an query set delete action!'
        )

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        model_object = self.query_set.get(id=body_data['data']['id'])

        method = getattr(model_object, body_data['data']['method'])

        return method(**body_data['data']['kwargs'])

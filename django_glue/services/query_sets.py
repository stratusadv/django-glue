from typing import Optional

from django.db.models import QuerySet

from django_glue.data_classes import GlueJsonResponseData, GlueBodyData, GlueMetaData, GlueJsonData
from django_glue.responses import generate_json_200_response_data, generate_json_404_response_data
from django_glue.services.services import Service
from django_glue.utils import decode_query_set_from_str, generate_simple_field_dict, get_field_names_from_model, \
    check_valid_method_kwargs, type_set_method_kwargs, field_name_included


class GlueQuerySetService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        # Query set is optional for lazy loading. Call load_query_set() before using it.
        self.query_set: Optional[QuerySet] = None

    def load_query_set(self):
        self.query_set = decode_query_set_from_str(self.meta_data.query_set_str)

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        if 'filter_params' in body_data['data']:
            data = []
            for model_object in self.query_set.filter(**body_data['data']['filter_params']):
                data.append(GlueJsonData(simple_fields=generate_simple_field_dict(
                        model_object, self.meta_data.fields, self.meta_data.exclude)))

        elif 'all' in body_data['data']:
            data = []
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

        # Todo: This is duplicated code
        for field_name in get_field_names_from_model(self.meta_data.model_class):
            if field_name in body_data['data'] and field_name != 'id':
                setattr(model_object, field_name, body_data['data'][field_name])

        model_object.save()

        json_data = GlueJsonData()

        json_data.simple_fields = generate_simple_field_dict(
            model_object,
            self.meta_data.fields,
            self.meta_data.exclude
        )

        return generate_json_200_response_data(
            'THE QUERY CREATE ACTION',
            'this is a response from an query set create action!',
            json_data
        )

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        model_object = self.meta_data.model_class.objects.get(id=body_data['data']['id'])

        # Todo: This is duplicated code
        for field_name in get_field_names_from_model(self.meta_data.model_class):
            if field_name in body_data['data'] and field_name != 'id' and field_name_included(field_name, self.meta_data.fields, self.meta_data.exclude):
                model_object.__dict__[field_name] = body_data['data'][field_name]

        model_object.save()

        return generate_json_200_response_data(
            'THE QUERY UPDATE ACTION',
            'this is a response from an query set update action!'
        )

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        if isinstance(body_data['data']['id'], list) or isinstance(body_data['data']['id'], tuple):
            self.query_set.filter(id__in=body_data['data']['id']).delete()

        elif isinstance(body_data['data']['id'], int):
            self.query_set.filter(id=body_data['data']['id']).delete()

        else:
            return generate_json_404_response_data()

        return generate_json_200_response_data(
            'THE QUERY DELETE ACTION',
            'this is a response from an query set delete action!'
        )

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_query_set()

        if isinstance(body_data['data']['id'], list) or isinstance(body_data['data']['id'], tuple):
            model_object = self.query_set.filter(id__in=body_data['data']['id'])

        elif isinstance(body_data['data']['id'], int):
            model_object = self.query_set.get(id=body_data['data']['id'])

        else:
            return generate_json_404_response_data()

        kwargs = body_data['data']['kwargs']
        method_return = None

        if body_data['data']['method'] in self.meta_data.methods and hasattr(self.meta_data.model_class, body_data['data']['method']):
            if isinstance(model_object, QuerySet):
                method_return = []
                for object in model_object:
                    method = getattr(object, body_data['data']['method'])
                    if check_valid_method_kwargs(method, kwargs):
                        type_set_kwargs = type_set_method_kwargs(method, kwargs)
                        method_return.append(method(**type_set_kwargs))

            elif isinstance(model_object, self.meta_data.model_class):
                method = getattr(model_object, body_data['data']['method'])

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
            'this is a response from an query set method action!',
            json_data
        )
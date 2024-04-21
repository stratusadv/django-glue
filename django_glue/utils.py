import inspect
import pickle, base64, json
import urllib.parse
from typing import Optional, Callable, Union

from django.db.models import Model
from django.core.serializers.json import DjangoJSONEncoder

from django_glue.core.utils import serialize_object_to_json


#
# def generate_field_dict(model_object: Model, fields: [list, tuple], exclude: Union[list, tuple]):
#     # Todo: Is this even being used?
#     # Creates a detailed dictionary of model fields
#     fields_dict = {}
#
#     model = type(model_object)
#     # print(model_dict)
#     # json_model = json.loads(serialize_object_to_json(model_object))[0]
#     # print(json_model)
#
#     for field in model._meta.fields:
#         try:
#             if field_name_included(field.name, fields, exclude):
#                 if hasattr(field, 'get_internal_type'):
#                     if field.name == 'id':
#                         # field_value = json_model['pk']
#                         field_value = model_object.pk
#                         field_attr = ''
#                     else:
#                         field_value = getattr(model_object, field.name)
#                         # field_value = json_model['fields'][field.name]
#                         field_attr = generate_field_attr_dict(field)
#
#                     # Todo: Field name logic is duplicated
#                     if field.many_to_one or field.one_to_one:
#                         field_name = field.name + '_id'
#                     else:
#                         field_name = field.name
#
#                     fields_dict[field_name] = {
#                         'type': field.get_internal_type(),
#                         'value': field_value,
#                         'html_attr': field_attr
#                     }
#
#                     #     GlueModelFieldData(
#                     #     type=field.get_internal_type(),
#                     #     value=field_value,
#                     #     html_attr=field_attr,
#                     # ).to_dict()
#
#         except:
#             raise f'Field "{field.name}" is invalid field or exclude for model type "{model.__class__.__name__}"'
#
#     # for key, val in fields_dict.items():
#     #     print(val)
#     #
#     # return fields_dict
#     return json.loads(json.dumps(fields_dict, cls=DjangoJSONEncoder))


def generate_simple_field_dict(model_object, fields, exclude):
    fields_dict = generate_field_dict(model_object, fields, exclude)
    simple_fields_dict = {}

    for key, val in fields_dict.items():
        simple_fields_dict[key] = val['value']

    return simple_fields_dict


def check_valid_method_kwargs(method: Callable, kwargs: Optional[dict]):
    for kwarg in kwargs:
        if kwarg not in inspect.signature(method).parameters.keys():
            return False
    return True


def type_set_method_kwargs(method: Callable, kwargs: Optional[dict]) -> dict:
    type_set_kwargs = {}

    # This is a dict consisting of all kwargs and there type annotations (If they have type annotations)
    annotations = inspect.getfullargspec(method).annotations

    for kwarg in kwargs:
        if kwarg in annotations:
            # Converts the kwarg to match the type specified in on the methods kwargs
            type_set_kwargs[kwarg] = inspect.getfullargspec(method).annotations[kwarg](kwargs[kwarg])
        else:
            # If there is not a type annotation, the value remains the same
            type_set_kwargs[kwarg] = kwargs[kwarg]

    return type_set_kwargs


def encode_unique_name(request, unique_name):
    return urllib.parse.quote(f'{unique_name}|{request.path_info}', safe='')

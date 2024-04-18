import inspect
import pickle, base64, json
import urllib.parse
from typing import Optional, Callable, Union

from django.db.models import Model
from django.core.serializers.json import DjangoJSONEncoder

from django_glue.core.utils import serialize_object_to_json


def decode_query_set_from_str(query_set_string):
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set.query)).decode()


def field_name_included(name, fields, exclude):
    included = False
    if name not in exclude or exclude[0] == '__none__':
        if name in fields or fields[0] == '__all__':
            included = True

    return included


def generate_field_attr_dict(field):
    return {
        'name': field.name,
        'label': ''.join(word.capitalize() for word in field.name.split('_')),
        'id': f'id_{field.name}',
        'help_text': field.help_text,
        'required': not field.null,
        'disabled': not field.editable,
        'hidden': field.hidden,
        'choices': field.choices,
        'maxlength': field.max_length,
    }
    # form_field = field.formfield()
    # return form_field.widget_attrs(form_field.widget)


def generate_field_dict(model_object: Model, fields: [list, tuple], exclude: Union[list, tuple]):
    # Todo: Is this even being used?
    # Creates a detailed dictionary of model fields
    fields_dict = {}

    model = type(model_object)
    # print(model_dict)
    # json_model = json.loads(serialize_object_to_json(model_object))[0]
    # print(json_model)

    for field in model._meta.fields:
        try:
            if field_name_included(field.name, fields, exclude):
                if hasattr(field, 'get_internal_type'):
                    if field.name == 'id':
                        # field_value = json_model['pk']
                        field_value = model_object.pk
                        field_attr = ''
                    else:
                        field_value = getattr(model_object, field.name)
                        # field_value = json_model['fields'][field.name]
                        field_attr = generate_field_attr_dict(field)

                    # Todo: Field name logic is duplicated
                    if field.many_to_one or field.one_to_one:
                        field_name = field.name + '_id'
                    else:
                        field_name = field.name

                    # fields_dict[field_name] = GlueModelFieldData(
                    #     type=field.get_internal_type(),
                    #     value=field_value,
                    #     html_attr=field_attr,
                    # ).to_dict()

        except:
            raise f'Field "{field.name}" is invalid field or exclude for model type "{model.__class__.__name__}"'

    # for key, val in fields_dict.items():
    #     print(val)
    #
    # return fields_dict
    return json.loads(json.dumps(fields_dict, cls=DjangoJSONEncoder))


def generate_method_list(model_object, methods: tuple) -> list:
    methods_list = list()

    model = type(model_object)

    if methods[0] != '__none__':
        for method in methods:
            if hasattr(model_object, method):
                methods_list.append(method)
            else:
                raise f'Method "{method}" is invalid for model type "{model.__class__.__name__}"'

    return methods_list


def generate_simple_field_dict(model_object, fields, exclude):
    fields_dict = generate_field_dict(model_object, fields, exclude)
    simple_fields_dict = {}

    for key, val in fields_dict.items():
        simple_fields_dict[key] = val['value']

    return simple_fields_dict


# Todo: Field name logic is duplicated
def get_field_names_from_model(model) -> list:
    field_names = []

    for field in model._meta.fields:
        if field.many_to_one or field.one_to_one:
            field_names.append(field.name + '_id')
        else:
            field_names.append(field.name)

    return field_names


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

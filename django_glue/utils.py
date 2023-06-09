import logging, pickle, base64, json

from django.core import exceptions, serializers

from django_glue.data_classes import GlueModelFieldData


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


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
    form_field = field.formfield()
    return form_field.widget_attrs(form_field.widget)


def generate_field_dict(model_object, fields, exclude):
    fields_dict = dict()

    model = type(model_object)
    json_model = json.loads(serialize_object_to_json(model_object))[0]

    for field in model._meta.fields:
        try:
            if field_name_included(field.name, fields, exclude):
                if hasattr(field, 'get_internal_type'):
                    if field.name == 'id':
                        field_value = json_model['pk']
                        field_attr = ''
                    else:
                        field_value = json_model['fields'][field.name]
                        field_attr = generate_field_attr_dict(field)

                    fields_dict[field.name] = GlueModelFieldData(
                        type=field.get_internal_type(),
                        value=field_value,
                        html_attr=field_attr,
                    ).to_dict()

        except:
            raise f'Field "{field.name}" is invalid field or exclude for model type "{model.__class__.__name__}"'

    return fields_dict


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


def get_fields_from_model(model):
    return [field for field in model._meta.fields]


def process_and_save_form_values(model_object, form_values_dict, fields, exclude):
    logging.warning(f'{model_object = }')

    try:
        for key, val in form_values_dict.items():
            if key != 'id':
                if field_name_included(key, fields, exclude):
                    model_object.__dict__[key] = val

        model_object.full_clean()
        model_object.save()
        logging.warning(f'{model_object = }')

    except exceptions.ValidationError as e:
        logging.warning(f'Validation Failed {e = }')
        return {
            'type': 'error',
            'message_dict': e.message_dict
        }

    else:
        logging.warning(f'Validation Successful')
        return {
            'type': 'success',
        }


def process_and_save_field_value(model_object, field_name, value, fields, exclude):
    logging.warning(f'{field_name = } {value = }')
    try:
        if field_name_included(field_name, fields, exclude):
            model_object.__dict__[field_name] = value
            model_object.full_clean()
            model_object.save()

    except exceptions.ValidationError as e:
        logging.warning(f'Validation Failed {e = }')
        return {
            'type': 'error',
            'message_dict': e.message_dict
        }

    else:
        return {
            'type': 'success',
        }


def serialize_object_to_json(model_object):
    return serializers.serialize('json', [model_object, ])



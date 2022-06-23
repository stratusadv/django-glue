import logging, json, pickle, base64
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse

GLUE_SESSION_NAME = 'django_glue'

GLUE_CONNECT_INPUT_METHODS = (
    'live',
    'form',
)

GLUE_CONNECT_INPUT_TYPES = (
    'input',
    'textarea',
)

GLUE_CONNECT_SUBMIT_METHODS = (
    'create',
    'update',
)

GLUE_METHOD_CHOICES = (
    ('vie', 'View'),
    ('cha', 'Change'),
    ('del', 'Delete'),
)

GLUE_RESPONSE_TYPES = (
    'success',
    'info',
    'warning',
    'error',
)


def add_model_object_glue(request, unique_name, model_object, method, fields=None, **kwargs):
    from django.db.models import Model
    if isinstance(model_object, Model):
        rs = get_glue_session(request)

        content_type = ContentType.objects.get_for_model(model_object)

        # Todo: Write check to ensure unique name does not exist in session data
        rs['context'][unique_name] = {
            'type': 'model_object',
            'method': method,
            'model': 'test_model',
            'content_app_label': content_type.app_label,
            'content_model': content_type.model,
            'object_id': model_object.pk,
        }

        model = type(model_object)
        if type(fields) is str:
            rs['context'][unique_name]['fields'] = generate_field_dict(model._meta.get_field(fields), model_object)

        elif fields is None:
            fields_dict = dict()
            for field in model._meta.fields:
                fields_dict[field.name] = generate_field_dict(field, model_object)

            rs['context'][unique_name]['fields'] = fields_dict
        else:
            raise TypeError('field argument must be a str object')
    else:
        raise TypeError('model_object is not valid it must be a Model')


def add_query_set_glue(request, unique_name, model_query_set, method):
    from django.db.models.query import QuerySet
    if isinstance(model_query_set, QuerySet):

        rs = get_glue_session(request)

        content_type = ContentType.objects.get_for_model(model_query_set.query.model)

        rs['context'][unique_name] = {
            'type': 'query_set',
            'method': method,
            'model': 'test_model',
            'content_app_label': content_type.app_label,
            'content_model': content_type.model,
        }

        rs['query_sets'][unique_name] = encode_query_set_to_str(model_query_set)

    else:
        raise TypeError(f'model_query_set is not valid it must be a QuerySet')


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def clean_glue_session(request):
    request.session[GLUE_SESSION_NAME] = dict()


def decode_query_set_from_str(query_set_string):
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set.query)).decode()


def get_glue_session(request):
    if GLUE_SESSION_NAME not in request.session:
        request.session[GLUE_SESSION_NAME] = dict()
    if 'context' not in request.session[GLUE_SESSION_NAME]:
        request.session[GLUE_SESSION_NAME]['context'] = dict()
    if 'query_sets' not in request.session[GLUE_SESSION_NAME]:
        request.session[GLUE_SESSION_NAME]['query_sets'] = dict()

    return request.session[GLUE_SESSION_NAME]


def generate_field_dict(model_field, model_object):
    if hasattr(model_field, 'get_internal_type'):
        field_type = model_field.get_internal_type()

        field_dict = {
            'type': field_type,
            'value': getattr(model_object, model_field.name)
        }
        return field_dict


def get_fields_from_model(model):
    return [field for field in model._meta.fields]


def generate_glue_attribute_string(unique_name, glue_type, method, **kwargs):
    attribute_string = f'glue-unique-name="{unique_name}" glue-type="{glue_type}" glue-method="{method}"'
    for key, val in kwargs.items():
        attribute_string += f' glue-{key.replace("_", "-")}="{val}"'

    return attribute_string


def generate_json_response(status, response_type: str, message_title, message_body, additional_data=None):
    if response_type not in GLUE_RESPONSE_TYPES:
        raise ValueError(f'response_type "{response_type}" is not a valid, choices are {GLUE_RESPONSE_TYPES}')

    return JsonResponse({
        'type': response_type,
        'message_title': message_title,
        'message_body': message_body,
        'data': additional_data
    }, status=status)


def generate_json_404_response():
    return generate_json_response('404', 'error', 'Request not Found',
                                  'The requested information, object or view you are looking for was not found.')


def process_and_save_form_values(model_object, form_values_dict):
    for key, val in form_values_dict.items():
        model_object.__dict__[key] = val
    model_object.save()


def process_and_save_field_value(model_object, field, value):
    model_object.__dict__[field] = value
    model_object.save()

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
    rs = get_glue_session(request)

    content_type = ContentType.objects.get_for_model(model_object)

    # Todo: Write check to ensure unique name does not exist in session data
    rs[unique_name] = {
        'method': method,
        'model': 'test_model',
        'content_app_label': content_type.app_label,
        'content_model': content_type.model,
        'object_id': model_object.pk,
    }

    model = type(model_object)
    if type(fields) is str:
        rs[unique_name]['fields'] = generate_field_dict(model._meta.get_field(fields), model_object)

    elif fields is None:
        fields_dict = dict()
        for field in model._meta.fields:
            fields_dict[field.name] = generate_field_dict(field, model_object)

        rs[unique_name]['fields'] = fields_dict
    else:
        raise TypeError('field argument must be a str object')


def add_model_query_set_glue(request, unique_name, model_object, model_query_set, method):
    import pickle
    import base64

    rs = get_glue_session(request)

    content_type = ContentType.objects.get_for_model(model_object)

    query_set = model_query_set.only('id')

    logging.warning(pickle.dumps(query_set))

    encoded_query_set = encode_query_set_to_str(query_set)
    logging.warning(encoded_query_set)

    decoded_query_set = decode_query_set_from_str(encoded_query_set)
    logging.warning(decode_query_set_from_str(encoded_query_set))

    for thing in decoded_query_set:
        logging.warning(thing.id)

    rs[unique_name] = {
        'method': method,
        'model': 'test_model',
        'content_app_label': content_type.app_label,
        'content_model': content_type.model,
        'object_id': model_object.pk,
        'query_set': encode_query_set_to_str(model_query_set),
    }


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def clean_glue_session(request):
    request.session[GLUE_SESSION_NAME] = dict()


def decode_query_set_from_str(query_set_string):
    return pickle.loads(base64.b64decode(query_set_string))


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set)).decode()


def get_glue_session(request):
    if GLUE_SESSION_NAME not in request.session:
        request.session[GLUE_SESSION_NAME] = dict()

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


def generate_json_response(status, response_type: str, message_title, message_body):
    if response_type not in GLUE_RESPONSE_TYPES:
        raise ValueError(f'response_type "{response_type}" is not a valid, choices are {GLUE_RESPONSE_TYPES}')

    return JsonResponse({
        'type': response_type,
        'message_title': message_title,
        'message_body': message_body,
    }, status=status)


def generate_json_404_response():
    return generate_json_response('404', 'error', 'Request not Found',
                                  'The requested information, object or view you are looking for was not found.')

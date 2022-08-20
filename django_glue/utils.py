import logging, pickle, base64, json

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import Http404

from django_glue.conf import settings

GLUE_ACCESS_TYPES = (
    'view',
    'add',
    'change',
    'delete',
)

GLUE_RESPONSE_TYPES = (
    'success',
    'info',
    'warning',
    'error',
    'debug',
)

GLUE_SESSION_TYPES = (
    'context',
    'query_set',
    'fields',
    'exclude',
)


def add_glue(request, unique_name: str, target, access: str, fields=('__all__',), exclude=('__none__',), **kwargs):
    if access in GLUE_ACCESS_TYPES:
        if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
            if unique_name_unused(request, unique_name):
                glue_session = get_glue_session(request)

                if isinstance(target, Model):
                    content_type = ContentType.objects.get_for_model(target)

                    glue_session['context'][unique_name] = {
                        'connection': 'model_object',
                        'access': access,
                        'app_label': content_type.app_label,
                        'model': content_type.model,
                        'object_id': target.pk,
                    }

                    glue_session['context'][unique_name]['fields'] = generate_field_dict(target, fields, exclude)

                elif isinstance(target, QuerySet):
                    content_type = ContentType.objects.get_for_model(target.query.model)

                    glue_session['context'][unique_name] = {
                        'connection': 'query_set',
                        'access': access,
                        'app_label': content_type.app_label,
                        'model': content_type.model,
                    }

                    glue_session['context'][unique_name]['fields'] = generate_field_dict(target.query.model(), fields, exclude)
                    glue_session['query_set'][unique_name] = encode_query_set_to_str(target)

                else:
                    raise TypeError(f'target is not a valid type must be django Model or QuerySet')

                glue_session['fields'][unique_name] = fields
                glue_session['exclude'][unique_name] = exclude
            else:
                raise ValueError(f'unique_name "{unique_name}" is already being used.')
        else:
            raise TypeError(f'fields or exclude is not a valid type must be a list or tuple')
    else:
        raise TypeError(f'access "{access}" is not a valid, choices are {GLUE_ACCESS_TYPES}')


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def clean_glue_session(request):
    request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()


def decode_query_set_from_str(query_set_string):
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set.query)).decode()


def generate_field_dict(model_object, fields, exclude):
    fields_dict = dict()

    model = type(model_object)

    for field in model._meta.fields:
        try:
            if field.name not in exclude or exclude[0] == '__none__':
                if field.name in fields or fields[0] == '__all__':
                    if hasattr(field, 'get_internal_type'):
                        fields_dict[field.name] = {
                            'type': field.get_internal_type(),
                            'value': getattr(model_object, field.name)
                        }

        except:
            raise f'Invalid field or exclude for model type {model.name}'

    return fields_dict


def generate_simple_field_dict(model_object, fields, exclude):
    fields_dict = generate_field_dict(model_object, fields, exclude)
    simple_fields_dict = {}

    for key, val in fields_dict.items():
        simple_fields_dict[key] = val['value']

    return simple_fields_dict


def get_fields_from_model(model):
    return [field for field in model._meta.fields]


def get_glue_session(request):
    if settings.DJANGO_GLUE_SESSION_NAME not in request.session:
        request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()
    for session_type in GLUE_SESSION_TYPES:
        if session_type not in request.session[settings.DJANGO_GLUE_SESSION_NAME]:
            request.session[settings.DJANGO_GLUE_SESSION_NAME][session_type] = dict()

    return request.session[settings.DJANGO_GLUE_SESSION_NAME]


def glue_access_check(access, access_level):
    if GLUE_ACCESS_TYPES.index(access) >= GLUE_ACCESS_TYPES.index(access_level):
        return True
    else:
        return False


def run_glue_method(request, model_object, method):
    if hasattr(model_object, method):
        getattr(model_object, method)(request)


def process_and_save_form_values(model_object, form_values_dict):
    logging.warning(f'{model_object = }')
    for key, val in form_values_dict.items():
        if key != 'id':
            model_object.__dict__[key] = val
    model_object.save()
    logging.warning(f'{model_object = }')


def process_and_save_field_value(model_object, field, value):
    logging.warning(f'{field = } {value = }')
    model_object.__dict__[field] = value
    model_object.save()


def unique_name_unused(request, unique_name):
    if unique_name in get_glue_session(request)['context']:
        return False
    else:
        return True





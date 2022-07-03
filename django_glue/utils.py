import logging, json, pickle, base64
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue import settings

GLUE_UPDATE_TYPES = (
    'live',
    'form',
)

GLUE_FORM_SUBMIT_TYPES = (
    'create',
    'update',
)

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


def add_glue(request, unique_name, target, access, fields=('__all__',), exclude=('__none__',), **kwargs):
    if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
        if isinstance(target, Model):
            add_model_object_glue(request, unique_name, target, access, fields, exclude, **kwargs)
        elif isinstance(target, QuerySet):
            add_query_set_glue(request, unique_name, target, access, fields, exclude, **kwargs)
        else:
            raise TypeError(f'target is not a valid type must be django Model or QuerySet')
    else:
        raise TypeError(f'fields or exclude is not a valid type must be a list or tuple')


def add_model_object_glue(request, unique_name, model_object, access, fields, exclude, **kwargs):
    if isinstance(model_object, Model):
        rs = get_glue_session(request)

        content_type = ContentType.objects.get_for_model(model_object)

        # Todo: Write check to ensure unique name does not exist in session data
        rs['context'][unique_name] = {
            'type': 'model_object',
            'access': access,
            'model': 'test_model',
            'content_app_label': content_type.app_label,
            'content_model': content_type.model,
            'object_id': model_object.pk,
        }

        rs['context'][unique_name]['fields'] = generate_field_dict(model_object, fields, exclude)

    else:
        raise TypeError('model_object is not valid it must be a Model')


def add_query_set_glue(request, unique_name, model_query_set, access, fields, exclude, **kwargs):
    if isinstance(model_query_set, QuerySet):

        rs = get_glue_session(request)

        content_type = ContentType.objects.get_for_model(model_query_set.query.model)

        rs['context'][unique_name] = {
            'type': 'query_set',
            'access': access,
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
    request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()


def decode_query_set_from_str(query_set_string):
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set.query)).decode()


def get_glue_session(request):
    if settings.DJANGO_GLUE_SESSION_NAME not in request.session:
        request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()
    if 'context' not in request.session[settings.DJANGO_GLUE_SESSION_NAME]:
        request.session[settings.DJANGO_GLUE_SESSION_NAME]['context'] = dict()
    if 'query_sets' not in request.session[settings.DJANGO_GLUE_SESSION_NAME]:
        request.session[settings.DJANGO_GLUE_SESSION_NAME]['query_sets'] = dict()

    return request.session[settings.DJANGO_GLUE_SESSION_NAME]


def generate_field_dict(model_object, fields, exclude):
    fields_dict = dict()

    model = type(model_object)

    for field in model._meta.fields:
        try:
            if field.name not in exclude or exclude[0] == '__none__':
                if field.name in fields or fields[0] == '__all__':
                    if hasattr(model, 'get_internal_type'):
                        field_type = model.get_internal_type()

                        fields_dict[field.name] = {
                            'type': field_type,
                            'value': getattr(model_object, field.name)
                        }
        except:
            raise f'Invalid field or exclude for model type {model.name}'

    return fields_dict


def get_fields_from_model(model):
    return [field for field in model._meta.fields]


def generate_glue_attribute(name, value):
    return f'{settings.DJANGO_GLUE_ATTRIBUTE_PREFIX}-{name.replace("_", "-")}="{value}" '


def generate_safe_glue_attribute_string(
        unique_name=None,
        connect=None,
        event=None,
        id=None,
        update=None,
        target=None,
        category=None,
        **kwargs,
):

    attribute_string = ''
    for key, val in locals().items():
        if val is not None:
            attribute_string += generate_glue_attribute(name=key, value=val)

    for key, val in kwargs.items():
        attribute_string += generate_glue_attribute(name=key, value=val)

    from django.utils.safestring import mark_safe
    return mark_safe(attribute_string)


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


def run_glue_method(request, model_object, method):
    if hasattr(model_object, method):
        getattr(model_object, method)(request)


def add_model_object(request, model_object, **kwargs):
    run_glue_method(request, model_object, 'django_glue_add')


def change_model_object(request, model_object, **kwargs):
    run_glue_method(request, model_object, 'django_glue_change')


def delete_model_object(request, model_object, **kwargs):
    run_glue_method(request, model_object, 'django_glue_delete')


def view_model_object(request, model_object, **kwargs):
    run_glue_method(request, model_object, 'django_glue_view')


def process_and_save_form_values(model_object, form_values_dict):
    for key, val in form_values_dict.items():
        model_object.__dict__[key] = val
    model_object.save()


def process_and_save_field_value(model_object, field, value):
    model_object.__dict__[field] = value
    model_object.save()

import logging

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue import settings
from django_glue.utils import generate_field_dict, encode_query_set_to_str

GLUE_UPDATE_TYPES = (
    'live',
    'form',
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

GLUE_SESSION_TYPES = (
    'context',
    'query_set',
    'fields',
    'exclude',
)


def add_glue(request, unique_name, target, access, fields=('__all__',), exclude=('__none__',), **kwargs):
    if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
        if unique_name_unused(request, unique_name):
            rs = get_glue_session(request)

            if isinstance(target, Model):
                content_type = ContentType.objects.get_for_model(target)

                rs['context'][unique_name] = {
                    'connection': 'model_object',
                    'access': access,
                    'app_label': content_type.app_label,
                    'model': content_type.model,
                    'object_id': target.pk,
                }

                rs['context'][unique_name]['fields'] = generate_field_dict(target, fields, exclude)

            elif isinstance(target, QuerySet):
                content_type = ContentType.objects.get_for_model(target.query.model)

                rs['context'][unique_name] = {
                    'connection': 'query_set',
                    'access': access,
                    'app_label': content_type.app_label,
                    'model': content_type.model,
                }

                rs['query_set'][unique_name] = encode_query_set_to_str(target)

            else:
                raise TypeError(f'target is not a valid type must be django Model or QuerySet')

            rs['fields'][unique_name] = fields
            rs['exclude'][unique_name] = exclude
        else:
            raise ValueError(f'unique_name "{unique_name}" is already being used.')
    else:
        raise TypeError(f'fields or exclude is not a valid type must be a list or tuple')


def clean_glue_session(request):
    request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()


def get_glue_session(request):
    if settings.DJANGO_GLUE_SESSION_NAME not in request.session:
        request.session[settings.DJANGO_GLUE_SESSION_NAME] = dict()
    for session_type in GLUE_SESSION_TYPES:
        if session_type not in request.session[settings.DJANGO_GLUE_SESSION_NAME]:
            request.session[settings.DJANGO_GLUE_SESSION_NAME][session_type] = dict()

    return request.session[settings.DJANGO_GLUE_SESSION_NAME]


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
    logging.warning(f'{model_object = }')
    for key, val in form_values_dict.items():
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


from types import FunctionType
from time import time

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue.classes import GlueKey
from django_glue.conf import settings
from django_glue.utils import encode_query_set_to_str, generate_field_dict

GLUE_ACCESS_TYPES = (
    'view',
    'add',
    'change',
    'delete',
)

GLUE_SESSION_TYPES = (
    'context',
    'query_set',
    'fields',
    'exclude',
)


def add_glue(
        request,
        unique_name: str,
        target, access: str,
        fields=('__all__',),
        exclude=('__none__',),
        **kwargs,
):
    if access in GLUE_ACCESS_TYPES:
        if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
            if glue_unique_name_unused(request, unique_name):
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

                    glue_session['context'][unique_name]['fields'] = generate_field_dict(target.query.model(), fields,
                                                                                         exclude)
                    glue_session['query_set'][unique_name] = encode_query_set_to_str(target)

                elif isinstance(target, FunctionType):
                    pass

                else:
                    raise TypeError(
                        f'target is not a valid type must be a Python Method, Django Model or Django QuerySet')

                glue_session['fields'][unique_name] = fields
                glue_session['exclude'][unique_name] = exclude

                set_glue_expiry_key(request, unique_name)
            else:
                raise ValueError(f'unique_name "{unique_name}" is already being used.')
        else:
            raise TypeError(f'fields or exclude is not a valid type must be a list or tuple')
    else:
        raise TypeError(f'access "{access}" is not a valid, choices are {GLUE_ACCESS_TYPES}')


def clean_glue_session(request):
    glue_expiry_keys_session = get_glue_expiry_keys_session(request)

    expired_key_list = list()

    expired_unique_name_set = set()
    active_unique_name_set = set()

    for key, val in glue_expiry_keys_session.items():
        if time() > val['expire_time']:
            expired_unique_name_set.update(val['unique_name_list'])
            expired_key_list.append(key)
        else:
            active_unique_name_set.update(val['unique_name_list'])

    for expired_key in expired_key_list:
        glue_expiry_keys_session.pop(expired_key)

    removable_unique_name_set = expired_unique_name_set.difference(active_unique_name_set)

    for unique_name in removable_unique_name_set:
        purge_unique_name_from_glue_session(request, unique_name)


def get_glue_session(request):
    request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, dict())
    for session_type in GLUE_SESSION_TYPES:
        request.session[settings.DJANGO_GLUE_SESSION_NAME].setdefault(session_type, dict())

    return request.session[settings.DJANGO_GLUE_SESSION_NAME]


def get_glue_expiry_keys_session(request):
    return request.session.setdefault(settings.DJANGO_GLUE_EXPIRY_KEYS_SESSION_NAME, dict())


def glue_access_check(access, access_level):
    if GLUE_ACCESS_TYPES.index(access) >= GLUE_ACCESS_TYPES.index(access_level):
        return True
    else:
        return False


def glue_unique_name_unused(request, unique_name):
    if unique_name in get_glue_session(request)['context']:
        return False
    else:
        return True


def glue_run_method(request, model_object, method):
    if hasattr(model_object, method):
        getattr(model_object, method)(request)


def purge_unique_name_from_glue_session(request, unique_name):
    glue_session = get_glue_session(request)
    for session_type in GLUE_SESSION_TYPES:
        if unique_name in glue_session[session_type]:
            glue_session[session_type].pop(unique_name)


def set_glue_expiry_key(request, unique_name):
    # Todo: Look at combining keys to reduce pings and data usage
    glue_expiry_keys_session = get_glue_expiry_keys_session(request)
    glue_key = GlueKey()
    print(glue_key.value)

    glue_expiry_keys_session.setdefault(
        glue_key.value,
        {
            'expire_time': time() + settings.DJANGO_GLUE_EXPIRY_KEY_TIME,
            'unique_name_list': [],
        }
    )

    if unique_name not in glue_expiry_keys_session[glue_key.value]['unique_name_list']:
        glue_expiry_keys_session[glue_key.value]['unique_name_list'].append(unique_name)



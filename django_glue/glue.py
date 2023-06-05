from types import FunctionType
from time import time

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue.conf import settings
from django_glue.utils import encode_query_set_to_str, generate_field_dict, generate_method_list

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
    'methods',
)


def add_glue(
        request,
        unique_name: str,
        target,
        access: str,
        fields=('__all__',),
        exclude=('__none__',),
        methods=('__none__',),
        **kwargs,
):
    if access in GLUE_ACCESS_TYPES:
        if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
            if glue_unique_name_unused(request, unique_name):
                purge_unique_name_from_glue_session(request, unique_name)

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
                glue_session['context'][unique_name]['methods'] = generate_method_list(target, methods)

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
                glue_session['context'][unique_name]['methods'] = generate_method_list(target.query.model(), methods)
                glue_session['query_set'][unique_name] = encode_query_set_to_str(target)

            elif isinstance(target, FunctionType):
                pass

            else:
                raise TypeError(
                    f'target is not a valid type must be a Django Glue Decorated Python Function, Django Model or Django QuerySet')

            glue_session['fields'][unique_name] = fields
            glue_session['exclude'][unique_name] = exclude

            set_glue_keep_live(request, unique_name)

            set_glue_session_modified(request)

        else:
            raise TypeError(f'fields or exclude is not a valid type must be a list or tuple')
    else:
        raise TypeError(f'access "{access}" is not a valid, choices are {GLUE_ACCESS_TYPES}')


def clean_glue_session(request):
    glue_keep_live_session = get_glue_keep_live_session(request)

    expired_session_list = list()

    expired_unique_name_set = set()
    active_unique_name_set = set()

    for key, val in glue_keep_live_session.items():
        if time() > val['expire_time']:
            expired_unique_name_set.update(val['unique_name_list'])
            expired_session_list.append(key)
        else:
            active_unique_name_set.update(val['unique_name_list'])

    for expired_session in expired_session_list:
        glue_keep_live_session.pop(expired_session)

    removable_unique_name_set = expired_unique_name_set.difference(active_unique_name_set)

    for unique_name in removable_unique_name_set:
        purge_unique_name_from_glue_session(request, unique_name)

    set_glue_session_modified(request)


def get_glue_session(request):
    request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, dict())

    for session_type in GLUE_SESSION_TYPES:
        request.session[settings.DJANGO_GLUE_SESSION_NAME].setdefault(session_type, dict())

    return request.session[settings.DJANGO_GLUE_SESSION_NAME]


def get_glue_keep_live_next_expire_time():
    return time() + settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS


def get_glue_keep_live_session(request):
    return request.session.setdefault(settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME, dict())


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


def set_glue_keep_live(request, unique_name):
    glue_keep_live_session = get_glue_keep_live_session(request)

    glue_keep_live_session.setdefault(
        request.path,
        {
            'expire_time': get_glue_keep_live_next_expire_time(),
            'unique_name_list': [],
        }
    )

    if unique_name not in glue_keep_live_session[request.path]['unique_name_list']:
        glue_keep_live_session[request.path]['unique_name_list'].append(unique_name)

    set_glue_session_modified(request)


def set_glue_session_modified(request):
    request.session.modified = True


def update_glue_keep_live(request, keep_live_path):
    glue_keep_live_session = get_glue_keep_live_session(request)
    if keep_live_path in glue_keep_live_session:
        glue_keep_live_session[keep_live_path]['expire_time'] = get_glue_keep_live_next_expire_time()


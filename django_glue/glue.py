from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue.sessions import GlueSession, GlueKeepLiveSession

GLUE_ACCESS_TYPES = (
    'view',
    'add',
    'change',
    'delete',
)

def add_glue(
        request,
        unique_name: str,
        target,
        access: str = 'view',
        fields: tuple =('__all__',),
        exclude: tuple =('__none__',),
        methods: tuple =('__none__',),
) -> None:
    if access in GLUE_ACCESS_TYPES:
        if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
            glue_session = GlueSession(request)

            if isinstance(target, Model):
                glue_session.add_model_object(unique_name, target, access, fields, exclude, methods)

            elif isinstance(target, QuerySet):
                glue_session.add_query_set(unique_name, target, access, fields, exclude, methods)

            else:
                raise f'target is not a valid type must be a Django Glue Decorated Python Function, Django Model or Django QuerySet'

            glue_keep_live_session = GlueKeepLiveSession(request)

            glue_keep_live_session.set_unique_name(unique_name)

            glue_session.set_modified()

        else:
            raise f'fields or exclude is not a valid type must be a list or tuple'
    else:
        raise f'access "{access}" is not a valid, choices are {GLUE_ACCESS_TYPES}'


def glue_access_check(access, access_level) -> bool:
    if GLUE_ACCESS_TYPES.index(access) >= GLUE_ACCESS_TYPES.index(access_level):
        return True
    else:
        return False


def glue_run_method(request, model_object, method):
    if hasattr(model_object, method):
        getattr(model_object, method)(request)




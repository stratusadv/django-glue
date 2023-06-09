from typing import Union

from django.db.models import Model
from django.db.models.query import QuerySet

from django_glue.sessions import GlueSession, GlueKeepLiveSession


def add_glue(
        request,
        unique_name: str,
        target,
        access: str = 'view',
        fields: Union[list, tuple] = ('__all__',),
        exclude: Union[list, tuple] = ('__none__',),
        methods: Union[list, tuple] = ('__none__',),
) -> None:
    if isinstance(fields, (list, tuple)) and isinstance(exclude, (list, tuple)):
        glue_session = GlueSession(request)

        if isinstance(target, Model):
            glue_session.add_model_object(unique_name, target, access, fields, exclude, methods)

        elif isinstance(target, QuerySet):
            glue_session.add_query_set(unique_name, target, access, fields, exclude, methods)

        else:
            raise f'target is not a valid type must be a django.db.models.Model or django.db.models.query.QuerySet'

        glue_keep_live_session = GlueKeepLiveSession(request)

        glue_keep_live_session.set_unique_name(unique_name)

        glue_session.set_modified()

    else:
        raise f'fields or exclude is not a valid type must be a list or tuple'

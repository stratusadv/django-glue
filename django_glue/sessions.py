from time import time

from django.contrib.contenttypes.models import ContentType

from django_glue.conf import settings
from django_glue.enums import GlueConnection, GlueAccess
from django_glue.types import GlueContextData, GlueMetaData
from django_glue.utils import generate_field_dict, generate_method_list, encode_query_set_to_str

GLUE_SESSION_TYPES = (
    'context',
    'meta',
    'query_set',
    'fields',
    'exclude',
    'methods',
)

class GlueSession:
    def __init__(self, request):
        self.request = request

        self.request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, dict())

        for session_type in GLUE_SESSION_TYPES:
            self.request.session[settings.DJANGO_GLUE_SESSION_NAME].setdefault(session_type, dict())

        self.session = self.request.session[settings.DJANGO_GLUE_SESSION_NAME]


    def __getitem__(self, key):
        return self.session[key]

    def __setitem__(self, key, value):
        self.session[key] = value

    def add_model_object(
            self,
            unique_name: str,
            model_object,
            access: str = 'view',
            fields: tuple = ('__all__',),
            exclude: tuple = ('__none__',),
            methods: tuple = ('__none__',),
    ):
        content_type = ContentType.objects.get_for_model(model_object)

        self.check_unique_name(unique_name)

        self.add_context(unique_name, GlueContextData(
            connection=GlueConnection('model_object'),
            access=GlueAccess(access),
            fields=generate_field_dict(model_object, fields, exclude),
            methods=generate_method_list(model_object, methods),
        ))

        self.add_meta(unique_name, GlueMetaData(
            app_label=content_type.app_label,
            model=content_type.model,
            object_pk=model_object.pk,
        ))

        self.add_fields(unique_name, fields)
        self.add_exclude(unique_name, exclude)
        self.add_methods(unique_name, methods)

    def add_query_set(
            self,
            unique_name: str,
            query_set,
            access: str = 'view',
            fields: tuple = ('__all__',),
            exclude: tuple = ('__none__',),
            methods: tuple = ('__none__',),
    ):
        content_type = ContentType.objects.get_for_model(query_set.query.model)

        self.check_unique_name(unique_name)

        self.add_context(unique_name, GlueContextData(
            connection=GlueConnection('query_set'),
            access=GlueAccess(access),
            fields=generate_field_dict(query_set.query.model(), fields, exclude),
            methods=generate_method_list(query_set.query.model(), methods),
        ))

        self.add_meta(unique_name, GlueMetaData(
            app_label=content_type.app_label,
            model=content_type.model,
            query_set_str=encode_query_set_to_str(query_set),
        ))

        self.add_fields(unique_name, fields)
        self.add_exclude(unique_name, exclude)
        self.add_methods(unique_name, methods)

    def add_context(self, unique_name, context_data: GlueContextData) -> None:
        self.session['context'][unique_name] = context_data.to_dict()

    def add_fields(self, unique_name, fields: tuple):
        self.session['fields'][unique_name] = fields

    def add_exclude(self, unique_name, exclude: tuple):
        self.session['exclude'][unique_name] = exclude

    def add_meta(self, unique_name, meta_data: GlueMetaData) -> None:
        self.session['meta'][unique_name] = meta_data.to_dict()
    def add_methods(self, unique_name, methods: tuple):
        self.session['methods'][unique_name] = methods

    def check_unique_name(self, unique_name):
        if self.unique_name_unused(unique_name):
            self.purge_unique_name(unique_name)

    def clean(self, removable_unique_name_set):
        for unique_name in removable_unique_name_set:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name):
        for session_type in GLUE_SESSION_TYPES:
            if unique_name in self.session[session_type]:
                self.session[session_type].pop(unique_name)

    def set_modified(self):
        self.request.session.modified = True

    def unique_name_unused(self, unique_name):
        if unique_name in self.session['context']:
            return False
        else:
            return True


class GlueKeepLiveSession:
    def __init__(self, request):
        self.request = request
        self.session = request.session.setdefault(settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME, dict())

    def __getitem__(self, key):
        return self.session[key]

    def __setitem__(self, key, value):
        self.session[key] = value

    def clean_and_get_expired_unique_name_set(self) -> set:
        expired_session_list = list()

        expired_unique_name_set = set()
        active_unique_name_set = set()

        for key, val in self.session.items():
            if time() > val['expire_time']:
                expired_unique_name_set.update(val['unique_name_list'])
                expired_session_list.append(key)
            else:
                active_unique_name_set.update(val['unique_name_list'])

        for expired_session in expired_session_list:
            self.session.pop(expired_session)

        self.set_modified()

        return expired_unique_name_set.difference(active_unique_name_set)

    @staticmethod
    def get_next_expire_time():
        return time() + settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS

    def set_unique_name(self, unique_name):

        self.session.setdefault(
            self.request.path,
            {
                'expire_time': self.get_next_expire_time(),
                'unique_name_list': [],
            }
        )

        if unique_name not in self.session[self.request.path]['unique_name_list']:
            self.session[self.request.path]['unique_name_list'].append(unique_name)

        self.set_modified()

    def set_modified(self):
        self.request.session.modified = True

    def update_url_path(self, url_path):
        if url_path in self.session:
            self.session[url_path]['expire_time'] = self.get_next_expire_time()

        self.set_modified()

from django.contrib.contenttypes.models import ContentType

from django_glue.conf import settings
from django_glue.access.enums import GlueAccess
from django_glue.handler.enums import GlueConnection
from django_glue.session.data import GlueSessionData, GlueMetaData
from django_glue.session.session import Session
from django_glue.utils import generate_field_dict, generate_method_list, encode_query_set_to_str
from django_glue.session.enums import GlueSessionTypes


class GlueSession(Session):
    """
        Used to add models, query sets, and other objects to the session.
    """
    def __init__(self, request):
        super().__init__(request)

        self.request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, dict())

        for session_type in GlueSessionTypes:
            self.request.session[settings.DJANGO_GLUE_SESSION_NAME].setdefault(session_type.value, dict())

        self.session = self.request.session[settings.DJANGO_GLUE_SESSION_NAME]

    def __getitem__(self, key):
        return self.session[key]

    def __setitem__(self, key, value):
        self.session[key] = value

    def add_function(
            self,
            unique_name: str,
            target: str,
    ):
        self.check_unique_name(unique_name)

        self.add_session_data()

        self.add_context(unique_name, GlueSessionData(
            connection=GlueConnection('function'),
            access=GlueAccess('view'),
        ))

        self.add_meta(unique_name, GlueMetaData(
            function=target,
        ))

        self.set_modified()

    def add_glue_entity(self, glue_entity: 'GlueEntity'):
        self.check_unique_name(glue_entity.unique_name)
        self.add_session_data(glue_entity.unique_name, glue_entity.to_session_data())
        self.set_modified()

    def add_session_data(self, unique_name, session_data: GlueSessionData) -> None:
        self.session[unique_name] = session_data.to_dict()

    def add_template(
            self,
            unique_name: str,
            template,
    ):
        # Todo: Need to change this to an entity
        self.check_unique_name(unique_name)

        self.add_context(unique_name, GlueSessionData(
            connection=GlueConnection('template'),
            access=GlueAccess('view'),
        ))

        self.add_meta(unique_name, GlueMetaData(
            template=template,
        ))

        self.set_modified()

    def add_meta(self, unique_name, meta_data: GlueMetaData) -> None:
        self.session['meta'][unique_name] = meta_data.to_dict()

    def check_unique_name(self, unique_name):
        if self.unique_name_unused(unique_name):
            self.purge_unique_name(unique_name)

    def clean(self, removable_unique_names):
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def has_unique_name(self, unique_name):
        return unique_name in self.session

    def purge_unique_name(self, unique_name):
        for session_type in GlueSessionTypes:
            if unique_name in self.session[session_type.value]:
                self.session[session_type.value].pop(unique_name)

    def set_modified(self):
        self.request.session.modified = True

    def unique_name_unused(self, unique_name):
        return unique_name in self.session

import json

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.conf import settings

from django_glue.session.data import GlueSessionData
from django_glue.session.session import Session


class GlueSession(Session):
    """
        Used to add models, query sets, and other objects to the session.
    """
    def __init__(self, request):
        super().__init__(request)
        self.request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, dict())
        self.session = self.request.session[settings.DJANGO_GLUE_SESSION_NAME]

    def __getitem__(self, key):
        return self.session[key]

    def __setitem__(self, key, value):
        self.session[key] = value

    def add_glue_entity(self, glue_entity: 'GlueEntity'):
        if glue_entity.unique_name in self.session:
            self.purge_unique_name(glue_entity.unique_name)

        self.add_session_data(glue_entity.unique_name, glue_entity.to_session_data())
        self.set_modified()

    def add_session_data(self, unique_name, session_data: GlueSessionData) -> None:
        self.session[unique_name] = session_data.to_dict()

    def clean(self, removable_unique_names):
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name):
        self.session.pop(unique_name)

    def set_modified(self):
        self.request.session.modified = True

    def to_json(self):
        return json.dumps(self.session, cls=DjangoJSONEncoder)

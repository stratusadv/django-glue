import json
from typing import Sequence

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.conf import settings
from django_glue.glue.glue import BaseGlue
from django_glue.session.data import SessionData
from django_glue.session.session import BaseGlueSession


class Session(BaseGlueSession):
    """
        Used to add models, query sets, and other objects to the session.
    """
    _session_key: str = settings.DJANGO_GLUE_SESSION_NAME

    def add_glue(self, glue: BaseGlue) -> None:
        if glue.unique_name in self.session:
            self.purge_unique_name(glue.unique_name)

        self.add_session_data(glue.unique_name, glue.to_session_data())
        self.set_modified()

    def add_session_data(self, unique_name: str, session_data: SessionData) -> None:
        self.session[unique_name] = session_data.to_dict()

    def clean(self, removable_unique_names: Sequence[str]) -> None:
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name: str) -> None:
        self.session.pop(unique_name)

    def to_json(self) -> str:
        return json.dumps(self.session, cls=DjangoJSONEncoder)

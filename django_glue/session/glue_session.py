import json
from typing import Any, Iterable

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest

from django_glue.conf import settings
from django_glue.glue.glue import BaseGlue
from django_glue.session.data import SessionData


class Session:
    """
        Used to add models, query sets, and other objects to the session.
    """
    def __init__(self, request: HttpRequest):
        self.request = request
        self.request.session.setdefault(settings.DJANGO_GLUE_SESSION_NAME, {})
        self.session = self.request.session[settings.DJANGO_GLUE_SESSION_NAME]

    def __getitem__(self, key: str) -> Any:
        return self.session[key]

    def __setitem__(self, key: str, value: Any):
        self.session[key] = value

    def add_glue(self, glue: BaseGlue) -> None:
        if glue.unique_name in self.session:
            self.purge_unique_name(glue.unique_name)

        self.add_session_data(glue.unique_name, glue.to_session_data())
        self.set_modified()

    def add_session_data(self, unique_name: str, session_data: SessionData) -> None:
        self.session[unique_name] = session_data.to_dict()

    def clean(self, removable_unique_names: Iterable[str]) -> None:
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name: str) -> None:
        self.session.pop(unique_name)

    def set_modified(self) -> None:
        self.request.session.modified = True

    def to_json(self) -> str:
        return json.dumps(self.session, cls=DjangoJSONEncoder)

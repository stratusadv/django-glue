import json
from typing import Sequence

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.conf import settings
from django_glue.glue.glue import BaseGlue
from django_glue.session.data import BaseGlueSessionData
from django_glue.session.session import BaseGlueSession


class Session(BaseGlueSession):
    """
        Used to add models, query sets, and other objects to the session.
    """
    _session_key: str = settings.DJANGO_GLUE_SESSION_NAME

    def clean(self, removable_unique_names: Sequence[str]) -> None:
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name: str) -> None:
        self.session.pop(unique_name)

    def to_json(self) -> str:
        return json.dumps(self.session, cls=DjangoJSONEncoder)

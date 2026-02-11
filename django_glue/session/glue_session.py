from __future__ import annotations

import json
from typing import Sequence, TYPE_CHECKING

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest

from django_glue import settings
from django_glue.glue.utils import get_glue_class_for_target_class
from django_glue.session.session import BaseGlueSession

if TYPE_CHECKING:
    from django_glue.glue.base import BaseGlue


class GlueSession(BaseGlueSession):
    """
        Used to add models, query sets, and other objects to the session.
    """
    _session_key: str = settings.DJANGO_GLUE_SESSION_NAME

    def __init__(self, request: HttpRequest):
        super().__init__(request)


    def get_glue_by_unique_name(self, unique_name: str) -> BaseGlue:
        glue_session_data = self.session.get(unique_name, None)
        if glue_session_data is None:
            # TODO: Raise GlueNotFoundError
            raise Exception()

        glue = get_glue_class_for_target_class(
            glue_session_data['target_class']
        ).from_session_kwargs(**glue_session_data)

        return glue

    def register_glue(self, glue: BaseGlue) -> None:
        if glue.unique_name in self.session:
            self.session.pop(glue.unique_name)

        self.session[glue.unique_name] = glue.to_session_data()
        self.set_modified()

    def clean(self, removable_unique_names: Sequence[str]) -> None:
        for unique_name in removable_unique_names:
            self.purge_unique_name(unique_name)

        self.set_modified()

    def purge_unique_name(self, unique_name: str) -> None:
        self.session.pop(unique_name)

    def to_json(self) -> str:
        return json.dumps(self.session, cls=DjangoJSONEncoder)

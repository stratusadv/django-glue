import json
from abc import ABC
from dataclasses import dataclass, asdict

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.access.access import GlueAccess
from django_glue.handler.enums import GlueConnection


@dataclass
class GlueSessionData(ABC):
    unique_name: str
    connection: GlueConnection
    access: GlueAccess

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), cls=DjangoJSONEncoder)
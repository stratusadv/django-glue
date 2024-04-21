from abc import ABC
from dataclasses import dataclass, asdict

from django_glue.access.access import GlueAccess
from django_glue.handler.enums import GlueConnection


@dataclass
class GlueSessionData(ABC):
    unique_name: str
    connection: GlueConnection
    access: GlueAccess

    def to_dict(self) -> dict:
        return asdict(self)

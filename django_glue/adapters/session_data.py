from dataclasses import dataclass

from django_glue import GlueAccess


@dataclass
class GlueSessionData:
    unique_name: str
    access: GlueAccess

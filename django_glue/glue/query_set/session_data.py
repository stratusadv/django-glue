from dataclasses import dataclass, field
from typing import Union

from django_glue.session.data import SessionData


@dataclass
class QuerySetGlueSessionData(SessionData):
    query_set_str: str
    fields: dict
    included_fields: Union[list, tuple]
    excluded_fields: Union[list, tuple]
    included_methods: Union[list, tuple]

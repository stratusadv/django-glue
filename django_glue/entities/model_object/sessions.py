from dataclasses import dataclass, field
from typing import Union

from django_glue.session.data import GlueSessionData


@dataclass
class GlueModelObjectSessionData(GlueSessionData):
    unique_name: str
    app_label: str
    model_name: str
    object_pk: int
    included_fields: Union[list, tuple]
    exclude_fields: Union[list, tuple]
    methods: Union[list, tuple]

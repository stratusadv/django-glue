from dataclasses import dataclass, field
from typing import Union

from django_glue.entities.model_object.responses import GlueModelField
from django_glue.session.data import GlueSessionData


@dataclass
class GlueModelObjectSessionData(GlueSessionData):
    app_label: str
    model_name: str
    object_pk: int
    fields: [GlueModelField]
    included_fields: Union[list, tuple]
    exclude_fields: Union[list, tuple]
    methods: Union[list, tuple]

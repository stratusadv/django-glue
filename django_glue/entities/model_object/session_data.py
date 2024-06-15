import uuid
from dataclasses import dataclass
from typing import Union

from django_glue.entities.model_object.fields.entities import GlueModelField
from django_glue.session.data import GlueSessionData


@dataclass
class GlueModelObjectSessionData(GlueSessionData):
    app_label: str
    model_name: str
    object_pk: Union[int, str, uuid.uuid4]
    fields: [GlueModelField]
    included_fields: Union[list, tuple]
    exclude_fields: Union[list, tuple]
    methods: Union[list, tuple]

    def __post_init__(self):
        if isinstance(self.object_pk, uuid.UUID):
            self.object_pk = str(self.object_pk)


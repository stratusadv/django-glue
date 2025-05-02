import uuid
from dataclasses import dataclass
from typing import Union

from django_glue.glue.model_object.fields.glue import ModelFieldGlue
from django_glue.session.data import SessionData


@dataclass
class ModelObjectGlueSessionData(SessionData):
    app_label: str
    model_name: str
    object_pk: Union[int, str, uuid.uuid4]
    fields: list[ModelFieldGlue]
    included_fields: Union[list, tuple]
    exclude_fields: Union[list, tuple]
    methods: Union[list, tuple]

    def __post_init__(self):
        if isinstance(self.object_pk, uuid.UUID):
            self.object_pk = str(self.object_pk)


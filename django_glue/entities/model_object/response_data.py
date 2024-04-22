from dataclasses import dataclass
from typing import Any


from django_glue.entities.model_object.fields import GlueModelFields
from django_glue.response.data import GlueJsonData


@dataclass
class GlueModelObjectJsonData(GlueJsonData):  # This is a little duplicated but allows us to send more response data.
    fields: GlueModelFields

    def to_dict(self):
        return self.fields.to_dict()


@dataclass
class MethodGlueModelObjectJsonData(GlueJsonData):
    method_return: Any

    def to_dict(self):
        return {'method_return': self.method_return}

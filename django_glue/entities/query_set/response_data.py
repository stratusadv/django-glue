from dataclasses import field, dataclass

from django_glue.entities.model_object.response_data import GlueModelObjectJsonData, MethodGlueModelObjectJsonData
from django_glue.response.data import GlueJsonData


@dataclass
class GlueQuerySetJsonData(GlueJsonData):
    model_objects: list[GlueModelObjectJsonData] = field(default_factory=list)

    def to_dict(self):
        return [model_object.to_dict() for model_object in self.model_objects]


@dataclass
class MethodGlueQuerySetJsonData(GlueJsonData):
    method_returns: list[MethodGlueModelObjectJsonData] = field(default_factory=list)

    def to_dict(self):
        return [method_return.to_dict() for method_return in self.method_returns]



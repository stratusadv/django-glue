from dataclasses import field, dataclass
from typing import Union

from django_glue.glue.model_object.response_data import GlueModelObjectJsonData, MethodGlueModelObjectJsonData
from django_glue.response.data import BaseJsonData


@dataclass
class GlueQuerySetJsonData(BaseJsonData):
    model_objects: list[GlueModelObjectJsonData] = field(default_factory=list)

    def to_dict(self):
        return [model_object.to_dict() for model_object in self.model_objects]


@dataclass
class MethodGlueQuerySetJsonData(BaseJsonData):
    method_returns: list[MethodGlueModelObjectJsonData] = field(default_factory=list)

    def to_dict(self):
        return [method_return.to_dict() for method_return in self.method_returns]


@dataclass
class ToChoicesGlueQuerySetJsonData(BaseJsonData):
    choices: list[Union[tuple, list]]

    def to_dict(self):
        return self.choices

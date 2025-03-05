from dataclasses import field, dataclass
from typing import Union

from django_glue.glue.model_object.response_data import ModelObjectGlueJsonData, MethodModelObjectGlueJsonData
from django_glue.response.data import BaseJsonData


@dataclass
class QuerySetGlueJsonData(BaseJsonData):
    model_objects: list[ModelObjectGlueJsonData] = field(default_factory=list)

    def to_dict(self):
        return [model_object.to_dict() for model_object in self.model_objects]


@dataclass
class MethodQuerySetGlueJsonData(BaseJsonData):
    method_returns: list[MethodModelObjectGlueJsonData] = field(default_factory=list)

    def to_dict(self):
        return [method_return.to_dict() for method_return in self.method_returns]


@dataclass
class ToChoicesQuerySetGlueJsonData(BaseJsonData):
    choices: list[Union[tuple, list]]

    def to_dict(self):
        return self.choices

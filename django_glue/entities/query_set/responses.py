from dataclasses import field, dataclass

from django_glue.entities.model_object.responses import GlueModelObjectJsonData
from django_glue.response.data import GlueJsonData


@dataclass
class GlueQuerySetJsonData(GlueJsonData):
    model_objects: list[GlueModelObjectJsonData] = field(default_factory=list)

    def to_dict(self):
        return [model_object.to_dict() for model_object in self.model_objects]

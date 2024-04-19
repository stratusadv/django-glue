from dataclasses import dataclass, field

from django_glue.entities.model_object.entities import GlueModelField
from django_glue.response.data import GlueJsonData


@dataclass
class GlueModelObjectJsonData(GlueJsonData):
    fields: list[GlueModelField] = field(default_factory=list)

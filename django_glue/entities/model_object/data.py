from dataclasses import dataclass, field

from django_glue.entities.model_object.entities import GlueModelField
from django_glue.response.data import GlueJsonData
from django_glue.session.data import GlueContextData, GlueMetaData


@dataclass
class GlueModelObjectContextData(GlueContextData):
    pass


@dataclass
class GlueModelObjectMetaData(GlueMetaData):
    pass


@dataclass
class GlueModelObjectJsonData(GlueJsonData):
    glue_fields: list[GlueModelField] = field(default_factory=list)


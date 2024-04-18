from dataclasses import dataclass

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
    pass

from dataclasses import dataclass

from django_glue.response.data import GlueContextData, GlueMetaData, GlueJsonData


@dataclass
class GlueModelObjectContextData(GlueContextData):
    pass


@dataclass
class GlueModelObjectMetaData(GlueMetaData):
    pass


@dataclass
class GlueModelObjectJsonData(GlueJsonData):
    pass

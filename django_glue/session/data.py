from abc import ABC
from typing import Union

from pydantic import BaseModel

from django_glue.access.access import Access
from django_glue.glue.enums import GlueType
from django_glue.glue.model_object.fields.glue import ModelFieldsGlue


class BaseGlueSessionData(ABC, BaseModel):
    unique_name: str
    glue_type: GlueType
    access: Access

class BaseModelGlueSessionData(BaseGlueSessionData):
    app_label: str
    model_class: str

class BaseModelObjectGlueSessionData(BaseModelGlueSessionData):
    data: dict

class BaseModelMetaGlueSessionData(BaseModelGlueSessionData):
    fields: ModelFieldsGlue
    methods: Union[list, tuple]
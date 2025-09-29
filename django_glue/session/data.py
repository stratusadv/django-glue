from abc import ABC
from typing import Union

from pydantic import BaseModel

from django_glue.access.access import Access
from django_glue.glue.enums import GlueType
from django_glue.glue.model_object.fields.glue import ModelFieldsGlue
from django_glue.glue.model_object.glue import ModelGlueInstanceFieldConfig


class BaseGlueSessionData(ABC, BaseModel):
    unique_name: str
    glue_type: GlueType
    access: Access

class BaseModelGlueSessionData(BaseGlueSessionData):
    app_label: str
    model_name: str
    data: dict = {}
    field_config: ModelGlueInstanceFieldConfig = ModelGlueInstanceFieldConfig()

class BaseModelMetaGlueSessionData(BaseModelGlueSessionData):
    fields: ModelFieldsGlue
    methods: Union[list, tuple]
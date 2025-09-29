from dataclasses import dataclass

from django_glue.glue.enums import GlueType
from django_glue.session.data import BaseModelGlueSessionData


@dataclass
class ModelObjectGlueSessionData(BaseModelGlueSessionData):
    glue_type = GlueType.MODEL_OBJECT
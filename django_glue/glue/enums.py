from enum import Enum
from typing import Type

from django_glue.access.actions import BaseAction
from django_glue.glue.function.actions import FunctionGlueAction
from django_glue.glue.function.session_data import FunctionGlueSessionData
from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.model_object.session_data import ModelObjectGlueSessionData
from django_glue.glue.query_set.actions import QuerySetGlueAction
from django_glue.glue.query_set.session_data import QuerySetGlueSessionData
from django_glue.glue.template.actions import TemplateGlueAction
from django_glue.glue.template.session_data import TemplateSessionData


class GlueType(str, Enum):
    MODEL_OBJECT = 'model_object'
    QUERY_SET = 'query_set'
    TEMPLATE = 'template'
    FUNCTION = 'function'

    def __str__(self) -> str:
        return self.value

    @property
    def action_type(self) -> Type[BaseAction]:
        match self:
            case GlueType.MODEL_OBJECT:
                return ModelObjectGlueAction
            case GlueType.QUERY_SET:
                return QuerySetGlueAction
            case GlueType.TEMPLATE:
                return TemplateGlueAction
            case GlueType.FUNCTION:
                return FunctionGlueAction
            case _:
                raise Exception('Invalid glue type')

    @property
    def session_data_type(self):
        match self:
            case GlueType.MODEL_OBJECT:
                return ModelObjectGlueSessionData
            case GlueType.QUERY_SET:
                return QuerySetGlueSessionData
            case GlueType.TEMPLATE:
                return TemplateSessionData
            case GlueType.FUNCTION:
                return FunctionGlueSessionData
            case _:
                raise Exception('Glue Type not found')

    @property
    def glue_class(self):
        match self:
            case GlueType.MODEL_OBJECT:
                from django_glue.glue.model_object.glue import ModelObjectGlue
                return ModelObjectGlue
            case GlueType.QUERY_SET:
                from django_glue.glue.query_set.glue import QuerySetGlue
                return QuerySetGlue
            case GlueType.TEMPLATE:
                from django_glue.glue.template.glue import TemplateGlue
                return TemplateGlue
            case GlueType.FUNCTION:
                from django_glue.glue.function.glue import FunctionGlue
                return FunctionGlue
            case _:
                raise Exception('Glue Type not found')
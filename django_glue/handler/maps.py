from django_glue.handler.enums import GlueConnection
from django_glue.entities.model_object.handlers import GetGlueModelObjectHandler


CONNECTION_TO_HANDLER_MAP = {
    GlueConnection.MODEL_OBJECT: GetGlueModelObjectHandler
}
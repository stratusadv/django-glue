from django_glue.handler.enums import GlueConnection
from django_glue.entities.model_object.handlers import GlueModelObjectRequestHandler


CONNECTION_TO_HANDLER_MAP = {
    GlueConnection.MODEL_OBJECT: GlueModelObjectRequestHandler
}
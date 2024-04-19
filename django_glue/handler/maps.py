from django_glue.entities.model_object.maps import GLUE_MODEL_OBJECT_HANDLER_MAP
from django_glue.entities.query_set.maps import GLUE_QUERY_SET_HANDLER_MAP
from django_glue.handler.enums import GlueConnection


CONNECTION_TO_HANDLER_MAP = {
    GlueConnection.MODEL_OBJECT: GLUE_MODEL_OBJECT_HANDLER_MAP,
    GlueConnection.QUERY_SET: GLUE_QUERY_SET_HANDLER_MAP
}

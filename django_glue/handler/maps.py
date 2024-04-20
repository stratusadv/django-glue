from django_glue.handler.enums import GlueConnection
from django_glue.entities.function.maps import GLUE_FUNCTION_HANDLER_MAP
from django_glue.entities.model_object.maps import GLUE_MODEL_OBJECT_HANDLER_MAP
from django_glue.entities.query_set.maps import GLUE_QUERY_SET_HANDLER_MAP
from django_glue.entities.template.maps import GLUE_TEMPLATE_HANDLER_MAP


CONNECTION_TO_HANDLER_MAP = {
    GlueConnection.MODEL_OBJECT: GLUE_MODEL_OBJECT_HANDLER_MAP,
    GlueConnection.QUERY_SET: GLUE_QUERY_SET_HANDLER_MAP,
    GlueConnection.FUNCTION: GLUE_FUNCTION_HANDLER_MAP,
    GlueConnection.TEMPLATE: GLUE_TEMPLATE_HANDLER_MAP
}

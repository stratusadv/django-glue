from django_glue.handler.enums import Connection
from django_glue.glue.function.maps import FUNCTION_GLUE_HANDLER_MAP
from django_glue.glue.model_object.maps import GLUE_MODEL_OBJECT_HANDLER_MAP
from django_glue.glue.query_set.maps import GLUE_QUERY_SET_HANDLER_MAP
from django_glue.glue.template.maps import GLUE_TEMPLATE_HANDLER_MAP


CONNECTION_TO_HANDLER_MAP = {
    Connection.MODEL_OBJECT: GLUE_MODEL_OBJECT_HANDLER_MAP,
    Connection.QUERY_SET: GLUE_QUERY_SET_HANDLER_MAP,
    Connection.FUNCTION: FUNCTION_GLUE_HANDLER_MAP,
    Connection.TEMPLATE: GLUE_TEMPLATE_HANDLER_MAP
}

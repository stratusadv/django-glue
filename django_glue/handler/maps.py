from django_glue.handler.enums import Connection
from django_glue.glue.function.maps import FUNCTION_GLUE_HANDLER_MAP
from django_glue.glue.model_object.maps import MODEL_OBJECT_GLUE_HANDLER_MAP
from django_glue.glue.query_set.maps import QUERY_SET_GLUE_HANDLER_MAP
from django_glue.glue.template.maps import TEMPLATE_GLUE_HANDLER_MAP


CONNECTION_TO_HANDLER_MAP = {
    Connection.MODEL_OBJECT: MODEL_OBJECT_GLUE_HANDLER_MAP,
    Connection.QUERY_SET: QUERY_SET_GLUE_HANDLER_MAP,
    Connection.FUNCTION: FUNCTION_GLUE_HANDLER_MAP,
    Connection.TEMPLATE: TEMPLATE_GLUE_HANDLER_MAP,
}

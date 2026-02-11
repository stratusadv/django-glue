from django_glue.glue.enums import GlueType
from django_glue.glue.function.maps import FUNCTION_GLUE_HANDLER_MAP
from django_glue.glue.model_object.maps import MODEL_OBJECT_GLUE_HANDLER_MAP
from django_glue.glue.query_set.maps import QUERY_SET_GLUE_HANDLER_MAP
from django_glue.glue.template.maps import TEMPLATE_GLUE_HANDLER_MAP


GLUE_TYPE_TO_HANDLER_MAP = {
    GlueType.MODEL_OBJECT: MODEL_OBJECT_GLUE_HANDLER_MAP,
    GlueType.QUERY_SET: QUERY_SET_GLUE_HANDLER_MAP,
    GlueType.FUNCTION: FUNCTION_GLUE_HANDLER_MAP,
    GlueType.TEMPLATE: TEMPLATE_GLUE_HANDLER_MAP,
}

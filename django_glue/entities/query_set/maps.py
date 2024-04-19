from django_glue.access.enums import GlueAction
from django_glue.entities.query_set import handlers


GLUE_MODEL_OBJECT_HANDLER_MAP = {
    GlueAction.GET: handlers.GetGlueQuerySetHandler,
    GlueAction.UPDATE: handlers.UpdateGlueQuerySetHandler,
    GlueAction.METHOD: handlers.MethodGlueQuerySetHandler,
    GlueAction.DELETE: handlers.DeleteGlueQuerySetHandler
}

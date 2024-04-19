from django_glue.access.enums import GlueAction
from django_glue.entities.model_object import handlers


GLUE_MODEL_OBJECT_HANDLER_MAP = {
    GlueAction.GET: handlers.GetGlueModelObjectHandler,
    GlueAction.UPDATE: handlers.UpdateGlueModelObjectHandler,
    GlueAction.METHOD: handlers.MethodGlueModelObjectHandler,
    GlueAction.DELETE: handlers.DeleteGlueModelObjectHandler
}

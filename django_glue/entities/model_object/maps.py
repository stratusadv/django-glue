from django_glue.entities.model_object.actions import GlueModelObjectAction
from django_glue.entities.model_object import handlers


GLUE_MODEL_OBJECT_HANDLER_MAP = {
    GlueModelObjectAction.GET: handlers.GetGlueModelObjectHandler,
    GlueModelObjectAction.UPDATE: handlers.UpdateGlueModelObjectHandler,
    GlueModelObjectAction.METHOD: handlers.MethodGlueModelObjectHandler,
    GlueModelObjectAction.DELETE: handlers.DeleteGlueModelObjectHandler
}

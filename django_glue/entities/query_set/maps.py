from django_glue.entities.query_set.actions import GlueQuerySetAction
from django_glue.entities.query_set import handlers


GLUE_QUERY_SET_HANDLER_MAP = {
    GlueQuerySetAction.ALL: handlers.AllGlueQuerySetHandler,
    GlueQuerySetAction.DELETE: handlers.DeleteGlueQuerySetHandler,
    GlueQuerySetAction.FILTER: handlers.FilterGlueQuerySetHandler,
    GlueQuerySetAction.GET: handlers.GetGlueQuerySetHandler,
    GlueQuerySetAction.NULL_OBJECT: handlers.NullObjectGlueQuerySetHandler,
    GlueQuerySetAction.METHOD: handlers.MethodGlueQuerySetHandler,
    GlueQuerySetAction.UPDATE: handlers.UpdateGlueQuerySetHandler,
    GlueQuerySetAction.TO_CHOICES: handlers.ToChoicesGlueQuerySetHandler,
}

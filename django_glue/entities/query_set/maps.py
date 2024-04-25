from django_glue.entities.query_set.actions import GlueQuerySetAction
from django_glue.entities.query_set import handlers


GLUE_QUERY_SET_HANDLER_MAP = {
    GlueQuerySetAction.ALL: handlers.AllGlueQuerySetHandler,
    GlueQuerySetAction.FILTER: handlers.FilterGlueQuerySetHandler,
    GlueQuerySetAction.GET: handlers.GetGlueQuerySetHandler,
    GlueQuerySetAction.UPDATE: handlers.UpdateGlueQuerySetHandler,
    GlueQuerySetAction.DELETE: handlers.DeleteGlueQuerySetHandler,
    GlueQuerySetAction.METHOD: handlers.MethodGlueQuerySetHandler,
}

from django_glue.glue.query_set import handlers
from django_glue.glue.query_set.actions import QuerySetGlueAction

QUERY_SET_GLUE_HANDLER_MAP = {
    QuerySetGlueAction.ALL: handlers.AllQuerySetGlueHandler,
    QuerySetGlueAction.DELETE: handlers.DeleteGlueQuerySetHandler,
    QuerySetGlueAction.FILTER: handlers.FilterGlueQuerySetHandler,
    QuerySetGlueAction.GET: handlers.GetGlueQuerySetHandler,
    QuerySetGlueAction.NULL_OBJECT: handlers.NullObjectGlueQuerySetHandler,
    QuerySetGlueAction.METHOD: handlers.MethodGlueQuerySetHandler,
    QuerySetGlueAction.UPDATE: handlers.UpdateGlueQuerySetHandler,
    QuerySetGlueAction.TO_CHOICES: handlers.ToChoicesGlueQuerySetHandler,
}

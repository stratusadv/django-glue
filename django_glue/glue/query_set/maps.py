from django_glue.glue.query_set import handlers
from django_glue.glue.query_set.actions import QuerySetGlueActionType

QUERY_SET_GLUE_HANDLER_MAP = {
    QuerySetGlueActionType.ALL: handlers.AllQuerySetGlueHandler,
    QuerySetGlueActionType.DELETE: handlers.DeleteGlueQuerySetHandler,
    QuerySetGlueActionType.FILTER: handlers.FilterGlueQuerySetHandler,
    QuerySetGlueActionType.GET: handlers.GetGlueQuerySetHandler,
    QuerySetGlueActionType.NULL_OBJECT: handlers.NullObjectGlueQuerySetHandler,
    QuerySetGlueActionType.METHOD: handlers.MethodGlueQuerySetHandler,
    QuerySetGlueActionType.UPDATE: handlers.UpdateGlueQuerySetHandler,
    QuerySetGlueActionType.TO_CHOICES: handlers.ToChoicesGlueQuerySetHandler,
}

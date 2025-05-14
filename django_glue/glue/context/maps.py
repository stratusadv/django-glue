from django_glue.glue.context import handlers
from django_glue.glue.context.actions import ContextGlueAction


CONTEXT_GLUE_HANDLER_MAP = {
    ContextGlueAction.GET: handlers.GetContextGlueHandler,
}

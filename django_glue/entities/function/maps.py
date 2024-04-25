from django_glue.entities.function.actions import GlueFunctionAction
from django_glue.entities.function import handlers


GLUE_FUNCTION_HANDLER_MAP = {
    GlueFunctionAction.CALL: handlers.CallGlueFunctionHandler,
}

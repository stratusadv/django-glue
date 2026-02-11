from django_glue.glue.function import handlers
from django_glue.glue.function.actions import FunctionGlueAction

FUNCTION_GLUE_HANDLER_MAP = {
    FunctionGlueAction.CALL: handlers.CallFunctionGlueHandler,
}

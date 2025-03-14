from django_glue.glue.function.actions import FunctionGlueAction
from django_glue.glue.function import handlers


FUNCTION_GLUE_HANDLER_MAP = {
    FunctionGlueAction.CALL: handlers.CallFunctionGlueHandler,
}

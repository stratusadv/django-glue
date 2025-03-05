from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.model_object import handlers


MODEL_OBJECT_GLUE_HANDLER_MAP = {
    ModelObjectGlueAction.GET: handlers.GetModelObjectGlueHandler,
    ModelObjectGlueAction.UPDATE: handlers.UpdateModelObjectGlueHandler,
    ModelObjectGlueAction.METHOD: handlers.MethodModelObjectGlueHandler,
    ModelObjectGlueAction.DELETE: handlers.DeleteModelObjectGlueHandler
}

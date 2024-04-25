from django_glue.entities.template.actions import GlueTemplateAction
from django_glue.entities.template import handlers


GLUE_TEMPLATE_HANDLER_MAP = {
    GlueTemplateAction.GET: handlers.GetGlueTemplateHandler,
}

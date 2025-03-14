from django_glue.glue.template import handlers
from django_glue.glue.template.actions import TemplateGlueAction

TEMPLATE_GLUE_HANDLER_MAP = {
    TemplateGlueAction.GET: handlers.GetTemplateGlueHandler,
}

from django_glue.glue.template.actions import TemplateGlueAction
from django_glue.glue.template import handlers


GLUE_TEMPLATE_HANDLER_MAP = {
    TemplateGlueAction.GET: handlers.GetTemplateGlueHandler,
}

from django_glue.glue.template.actions import TemplateGlueAction
from django_glue.glue.template import handlers


TEMPLATE_GLUE_HANDLER_MAP = {
    TemplateGlueAction.GET: handlers.GetTemplateGlueHandler,
}

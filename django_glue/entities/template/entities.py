from django.http import HttpResponse
from django.template.loader import render_to_string

from django_glue.access.access import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.template.responses import GlueTemplateJsonData
from django_glue.entities.template.sessions import TemplateSessionData
from django_glue.handler.enums import GlueConnection


class GlueTemplate(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            template_name: str,
    ):
        super().__init__(unique_name, GlueConnection.TEMPLATE, GlueAccess.VIEW)
        self.template_name = template_name

    def render_to_string(self, context_data: dict) -> str:
        return render_to_string(self.template_name, context_data)

    def to_session_data(self) -> TemplateSessionData:
        return TemplateSessionData(
            unique_name=self.unique_name,
            connection=self.connection,
            access=self.access,
            template_name=self.template_name
        )

    def to_response_data(self, rendered_template: str) -> GlueTemplateJsonData:
        return GlueTemplateJsonData(rendered_template)

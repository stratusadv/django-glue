from django.template.loader import render_to_string

from django_glue.access.access import Access
from django_glue.glue.glue import BaseGlue
from django_glue.glue.template.response_data import TemplateGlueJsonData
from django_glue.glue.template.session_data import TemplateSessionData
from django_glue.glue.enums import GlueType


class TemplateGlue(BaseGlue):
    def __init__(
            self,
            unique_name: str,
            template_name: str,
    ):
        super().__init__(unique_name, GlueType.TEMPLATE, Access.VIEW)
        self.template_name = template_name

    def render_to_string(self, context_data: dict) -> str:
        return render_to_string(self.template_name, context_data)

    def to_session_data(self) -> TemplateSessionData:
        return TemplateSessionData(
            unique_name=self.unique_name,
            glue_type=self.glue_type,
            access=self.access,
            template_name=self.template_name
        )

    def to_response_data(self, rendered_template: str) -> TemplateGlueJsonData:
        return TemplateGlueJsonData(rendered_template)

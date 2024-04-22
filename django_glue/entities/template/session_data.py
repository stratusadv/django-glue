from dataclasses import dataclass

from django_glue.session.data import GlueSessionData


@dataclass
class TemplateSessionData(GlueSessionData):
    template_name: str


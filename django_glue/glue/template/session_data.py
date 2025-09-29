from dataclasses import dataclass

from django_glue.session.data import BaseGlueSessionData


@dataclass
class TemplateSessionData(BaseGlueSessionData):
    template_name: str


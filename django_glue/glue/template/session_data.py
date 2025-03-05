from dataclasses import dataclass

from django_glue.session.data import SessionData


@dataclass
class TemplateSessionData(SessionData):
    template_name: str


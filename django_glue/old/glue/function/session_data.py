from dataclasses import dataclass

from django_glue.session.data import SessionData


@dataclass
class FunctionGlueSessionData(SessionData):
    function_path: str


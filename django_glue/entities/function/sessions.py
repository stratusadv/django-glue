from dataclasses import dataclass

from django_glue.session.data import GlueSessionData


@dataclass
class FunctionSessionData(GlueSessionData):
    function_path: str


from dataclasses import dataclass

from django_glue.session.data import GlueSessionData


@dataclass
class FunctionGlueSessionData(GlueSessionData):
    function_path: str


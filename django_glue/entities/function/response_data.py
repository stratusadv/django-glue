from dataclasses import dataclass
from typing import Any

from django_glue.response.data import GlueJsonData


@dataclass
class GlueFunctionJsonData(GlueJsonData):
    function_return: Any

    def to_dict(self):
        return {'function_return': self.function_return}
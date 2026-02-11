from dataclasses import dataclass
from typing import Any

from django_glue.response.data import BaseJsonData


@dataclass
class FunctionGlueJsonData(BaseJsonData):
    function_return: Any

    def to_dict(self) -> dict:
        return {'function_return': self.function_return}

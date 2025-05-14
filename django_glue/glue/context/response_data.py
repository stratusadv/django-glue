from dataclasses import dataclass
from typing import Any

from django_glue.response.data import BaseJsonData


@dataclass
class ContextGlueJsonData(BaseJsonData):
    context_data: dict[str, Any]

    def to_dict(self) -> dict:
        return {'context_data': self.context_data}

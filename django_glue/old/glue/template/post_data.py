from dataclasses import dataclass
from typing import Any


@dataclass
class GetTemplateGluePostData:
    context_data: dict[str, Any]


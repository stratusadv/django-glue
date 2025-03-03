from dataclasses import dataclass
from typing import Any


@dataclass
class GetGlueTemplatePostData:
    context_data: dict[str, Any]


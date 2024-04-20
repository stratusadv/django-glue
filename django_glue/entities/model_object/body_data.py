from dataclasses import dataclass
from typing import Any


@dataclass
class UpdateGlueObjectPostData:
    fields: dict[str, Any]

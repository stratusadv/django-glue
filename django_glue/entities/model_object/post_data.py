from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class GetGlueObjectPostData:
    id: Optional[int]


@dataclass
class UpdateGlueObjectPostData:
    id: Optional[int]
    fields: dict[str, Any]


@dataclass
class MethodGlueObjectPostData:
    id: Optional[int]
    kwargs: dict[str, Any]
    method: str

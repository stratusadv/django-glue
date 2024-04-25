from dataclasses import dataclass
from typing import Any


@dataclass
class CallGlueFunctionPostData:
    kwargs: dict[str, Any]

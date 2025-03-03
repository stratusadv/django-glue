from dataclasses import dataclass
from typing import Any


@dataclass
class CallFunctionGluePostData:
    kwargs: dict[str, Any]

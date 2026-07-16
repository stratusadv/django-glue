from dataclasses import dataclass
from typing import Any, ClassVar, Iterable

from django_glue.message import GlueMessage


@dataclass
class GlueResponse:
    Message: ClassVar[type] = GlueMessage

    result: Any = None
    messages: Iterable[GlueMessage] | None = None
    status: int = 200

    def __post_init__(self) -> None:
        self.messages = list(self.messages or [])

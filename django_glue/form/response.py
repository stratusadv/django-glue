from enum import Enum
from typing import Any


class JsonFormResponse:
    class Type(Enum):
        ERROR = 'ERROR'
        SUCCESS = 'SUCCESS'
        WARNING = 'WARNING'
        INFO = 'INFO'

    def __init__(
        self,
        type: Type = Type.SUCCESS,
        messages: list[str] | None = None,
        payload: dict[str, Any] | None = None
    ):
        self.type = type
        self.messages = messages
        self.payload = payload

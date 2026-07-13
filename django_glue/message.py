from dataclasses import dataclass

from django_glue.enums import MessageLevel
from django.contrib.messages import Message


@dataclass
class GlueMessage(Message):
    Level = MessageLevel

    def __init__(self, level: MessageLevel, message: str, extra_tags: str | None = None) -> None:
        super().__init__(level=level.value, message=message, extra_tags=extra_tags)

    @classmethod
    def debug(cls, message: str):
        return GlueMessage(level=MessageLevel.DEBUG, message=message)

    @classmethod
    def error(cls, message: str):
        return GlueMessage(level=MessageLevel.ERROR, message=message)

    @classmethod
    def info(cls, message: str):
        return GlueMessage(level=MessageLevel.INFO, message=message)

    @classmethod
    def success(cls, message: str):
        return GlueMessage(level=MessageLevel.SUCCESS, message=message)

    @classmethod
    def warning(cls, message: str):
        return GlueMessage(level=MessageLevel.WARNING, message=message)

    def to_dict(self) -> dict:
        return {
            'level': self.level,
            'level_tag': self.level_tag,
            'message': self.message,
            'tags': self.tags,
        }

from dataclasses import dataclass
from typing import Any, ClassVar, Iterable

from django.urls import reverse

from django_glue.message import GlueMessage


@dataclass
class GlueResponse:
    Message: ClassVar[type] = GlueMessage

    result: Any = None
    messages: Iterable[GlueMessage] | None = None
    status: int = 200

    def __post_init__(self) -> None:
        self.messages = list(self.messages or [])


class GlueRedirectResponse:
    def __new__(cls, view_name: str, **kwargs) -> GlueResponse:
        return GlueResponse(
            result={
                'redirect': {
                    'url': reverse(
                        'django_spire:auth:user:page:detail', kwargs=kwargs
                    )
                }
            }
        )

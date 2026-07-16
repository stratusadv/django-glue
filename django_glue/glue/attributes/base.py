from abc import ABC, abstractmethod
from typing import Any

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueRequestError


class BaseGlueAttribute(ABC):
    def __init__(self, *, name: str, required_access: GlueAccess, is_callable: bool) -> None:
        self.name = name
        self.required_access = required_access
        self.is_callable = is_callable

    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_value(self) -> Any:
        # TODO: change these to something attribute specific
        raise GlueRequestError(
            code='attribute_not_readable',
            message=f"Attribute '{self.name}' is not readable.",
            details={'attribute': self.name},
            status=422,
        )

    def set_value(self, value: Any) -> None:
        raise GlueRequestError(
            code='attribute_not_writable',
            message=f"Attribute '{self.name}' is not writable.",
            details={'attribute': self.name},
            status=422,
        )


    # TODO: context - should not be dict
    def call(self, kwargs: dict[str, Any], context: dict[str, Any]) -> Any:
        raise GlueRequestError(
            code='attribute_not_callable',
            message=f"Attribute '{self.name}' is not callable.",
            details={'attribute': self.name},
            status=422,
        )

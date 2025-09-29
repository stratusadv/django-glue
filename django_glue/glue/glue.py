from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union, TYPE_CHECKING, Type

from django_glue.access.access import Access
from django_glue.access.actions import GlueAction
from django_glue.glue.enums import GlueType

if TYPE_CHECKING:
    from django_glue.session.data import SessionData


class BaseGlue(ABC):
    glue_type: GlueType | None = None
    session_data_type: Type[SessionData] | None = None

    def __init__(
            self,
            unique_name: str,
            access: Union[Access, str] = Access.VIEW,
    ):
        if isinstance(access, str):
            self.access = Access(access)
        else:
            self.access = access
        self.unique_name = unique_name

    def __init_subclass__(cls, **kwargs):
        if not isinstance(cls.glue_type, GlueType):
            raise TypeError(f'glue_type on {cls.__name__} must be an instance of GlueType')
        if not issubclass(cls.session_data_type, SessionData):
            raise TypeError(f'session_data_type on {cls.__name__} must subclass SessionData')

    @abstractmethod
    def to_session_data(self) -> SessionData:
        pass

    @abstractmethod
    def process_action(self, action: GlueAction) -> :
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from django_glue.access.access import Access

if TYPE_CHECKING:
    from django_glue.glue.enums import GlueType
    from django_glue.session.data import SessionData


class BaseGlue(ABC):
    def __init__(
        self,
        unique_name: str,
        glue_type: GlueType,
        access: Access | str = Access.VIEW,
    ):
        self.unique_name = unique_name
        self.glue_type = glue_type

        if isinstance(access, str):
            self.access = Access(access)
        else:
            self.access = access

    @abstractmethod
    def to_session_data(self) -> SessionData:
        pass

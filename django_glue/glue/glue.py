from abc import ABC, abstractmethod
from typing import Union

from django_glue.access.access import Access
from django_glue.handler.enums import Connection


class BaseGlue(ABC):

    def __init__(
            self,
            unique_name: str,
            connection: Connection,
            access: Union[Access, str] = Access.VIEW,
    ):

        self.unique_name = unique_name
        self.connection = connection

        if isinstance(access, str):
            self.access = Access(access)
        else:
            self.access = access

    @abstractmethod
    def to_session_data(self) -> 'GlueSessionData':
        pass

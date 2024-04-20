from abc import ABC, abstractmethod
from typing import Union

from django_glue.access.enums import GlueAccess
from django_glue.handler.enums import GlueConnection


class GlueEntity(ABC):

    def __init__(
            self,
            unique_name: str,
            connection: GlueConnection,
            access: Union[GlueAccess, str] = GlueAccess.VIEW,
    ):

        self.unique_name = unique_name
        self.connection = connection

        if isinstance(access, str):
            self.access = GlueAccess(access)
        else:
            self.access = access

    @abstractmethod
    def to_response_data(self, *args, **kwargs) -> 'GlueJsonData':
        pass

    @abstractmethod
    def to_session_data(self) -> 'GlueSessionData':
        pass

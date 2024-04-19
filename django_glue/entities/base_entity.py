from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GlueEntity(ABC):

    @abstractmethod
    def to_session_data(self) -> 'GlueSessionData':
        pass

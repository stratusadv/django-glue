from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GlueFormField(ABC):
    pass

    @abstractmethod
    def to_dict(self):
        pass


class GlueCharField(GlueFormField):
    max_length: int

    def to_dict(self):
        field_dict = super().to_dict()
        return field_dict


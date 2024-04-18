from abc import ABC
from dataclasses import dataclass


@dataclass
class FormField(ABC):
    pass


class CharField(FormField):
    pass


from dataclasses import dataclass
from typing import Union


@dataclass
class FilterGlueQuerySetPostData:
    filter_params: dict[str, str]


@dataclass
class GetGlueQuerySetPostData:
    id: int


@dataclass
class DeleteGlueQuerySetPostData:
    id: list[int]

    def __post_init__(self):
        if isinstance(self.id, int):
            self.id = [id]

        if isinstance(self.id, str):
            return [int(str(self.id))]


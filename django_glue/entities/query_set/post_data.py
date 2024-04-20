from dataclasses import dataclass
from typing import Union, Any


@dataclass
class DeleteGlueQuerySetPostData:
    id: list[int]

    def __post_init__(self):
        if isinstance(self.id, int):
            self.id = [id]

        if isinstance(self.id, str):
            return [int(str(self.id))]


@dataclass
class FilterGlueQuerySetPostData:
    filter_params: dict[str, str]


@dataclass
class GetGlueQuerySetPostData:
    id: int


@dataclass
class MethodGlueQuerySetPostData:
    id: list[int]
    method: str
    kwargs: dict[str, Any]

    def __post_init__(self):
        if isinstance(self.id, int):
            self.id = [id]

        if isinstance(self.id, str):
            return [int(str(self.id))]


@dataclass
class UpdateGlueQuerySetPostData:
    id: int
    fields: dict[str, Any]

    def __post_init__(self):
        if isinstance(self.id, str):
            return [int(str(self.id))]

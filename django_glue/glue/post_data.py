from dataclasses import dataclass
from typing import Any, Optional, Union


# Model objects can be used from a queryset. Queryset and model object post data must be the same.
@dataclass
class BasePostData:
    id: int

    # def __post_init__(self):
    #     if isinstance(self.id, int):
    #         self.id = [self.id]
    #     elif isinstance(self.id, str):
    #         self.id = [int(self.id)]


@dataclass
class DeletePostData(BasePostData):
    pass


@dataclass
class GetPostData(BasePostData):
    pass


@dataclass
class MethodPostData(BasePostData):
    method: str
    kwargs: dict[str, Any]


@dataclass
class UpdatePostData(BasePostData):
    fields: dict[str, Any]

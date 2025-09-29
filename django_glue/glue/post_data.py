from typing import Any

from pydantic import BaseModel


# Model objects can be used from a queryset. Queryset and model object post data must be the same.

class BaseActionKwargs(BaseModel):
    pass

class MethodActionKwargs(BaseActionKwargs):
    method: str
    kwargs: dict[str, Any]


class UpdateActionKwargs(BaseActionKwargs):
    fields: dict[str, Any]

from typing import Callable

from pydantic import BaseModel

from django_glue.access.access import GlueAccess
from django_glue.utils import get_attr_from_path_string


class GlueAction(BaseModel):
    name: str
    parameters: dict[str, str | None]
    required_access: GlueAccess
    target_class_path: str

    @property
    def target_class(self) -> type:
        target_class = get_attr_from_path_string(self.target_class_path)
        if not isinstance(target_class, type):
            raise ValueError('target_class_path for instance does not refer to a valid class.')

        return target_class

    @property
    def callable(self) -> Callable:
        target_class = self.target_class
        action_function = getattr(self.target_class, self.name, None)

        if not action_function or not isinstance(action_function, Callable):
            raise ValueError(f'Could not find valid callable named {self.name} on action target class {target_class.__name__}')

        return action_function

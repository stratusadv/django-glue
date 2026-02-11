from __future__ import annotations

import inspect
from abc import ABC
from typing import Any

from pydantic import BaseModel

from django_glue.access.access import GlueAccess
from django_glue import data_transfer_objects as dto


class BaseGlue(ABC):
    target_class: type
    actions = {}

    def __init__(
        self,
        target: Any,
        unique_name: str,
        access: GlueAccess | str = GlueAccess.VIEW,
        **kwargs
    ):
        if not isinstance(target, self.target_class):
            raise ValueError(
                f"The value passed to 'target' for {self.__class__} must be an instance of {self.target_class.__name__} (according to the type assigned to '{self.__class__.__name__}.obj_class').")

        self.unique_name = unique_name

        if isinstance(access, GlueAccess):
            self.access = access
        else:
            self.access = GlueAccess(access)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, 'target_class'):
            raise TypeError(f"BaseGlue subclass {cls.__name__} must define 'target_class' attribute that matches the expected type of the __init__ 'target' parameter.")
        
        for attr_name, attr_value in cls.__dict__.items():
            if hasattr(attr_value, '_required_glue_access'):
                parameters = inspect.signature(attr_value).parameters
                parameter_data = {}

                for param_name, param_value in parameters.items():
                    if param_name in ['args', 'kwargs', 'self']:
                        continue
                    else:
                        parameter_data[param_name] = param_value.annotation

                cls.actions[attr_name] = (
                    attr_value,
                    parameter_data,
                    attr_value._required_glue_access
                )

    @classmethod
    def from_session_kwargs(cls, access: GlueAccess, unique_name: str, **kwargs) -> BaseGlue:
        return cls(
            access=access,
            unique_name=unique_name,
            **kwargs
        )

    def to_context_data(self):
        actions_data = {
            action_name: dict(action_parameters)
            for action_name, (_, action_parameters, _) in self.actions.items()
        }

        return dict(
            actions=actions_data,
            **self._get_context_data()
        )

    def _get_session_data(self) -> dict:
        return {}

    def _get_context_data(self) -> dict:
        return {}

    def to_session_data(self) -> dict:
        return dict(
            unique_name=self.unique_name,
            target_class=self.target_class.__name__,
            access=self.access
        ) | self._get_session_data()

    def process_request_data(self,
                             request_data: dto.GlueRequestData) -> dto.GlueResponseData:
        if not hasattr(self, request_data.action):
            raise TypeError(
                f"Instance of {type(self).__name__} must define '{request_data.action}' method to process this action.")

        if request_data.action not in self.actions:
            raise TypeError(
                f"Action method '{request_data.action}' must be decorated with '@action(access=GlueAccess.<REQUIRED_ACCESS>)' to specify required access.")

        action_func, action_parameters, required_access = self.actions[request_data.action]

        if not self.access.has_access(required_access):
            raise PermissionError(
                f"Insufficient access to perform '{request_data.action}' action.")

        if 'payload' not in action_parameters:
            if request_data.payload is not None:
                raise ValueError('This action does not support a payload parameter.')

            return action_func(self)
        else:
            return action_func(self, dict(**request_data.payload))

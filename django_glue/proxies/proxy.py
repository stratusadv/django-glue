from __future__ import annotations

import inspect
from abc import ABC
from typing import Any

from django_glue.access.access import GlueAccess
from django_glue import data_transfer_objects as dto


class BaseGlueProxy(ABC):
    subject_type: type
    actions = {}

    def __init__(
        self,
        target: Any,
        unique_name: str,
        access: GlueAccess | str = GlueAccess.VIEW,
        **kwargs
    ):
        if not isinstance(target, self.subject_type):
            raise ValueError(
                f"The value passed to 'target' for {self.__class__} must be an instance of {self.subject_type.__name__} (according to the type assigned to '{self.__class__.__name__}.obj_class').")

        self.unique_name = unique_name

        if isinstance(access, GlueAccess):
            self.access = access
        else:
            self.access = GlueAccess(access)

        self.target = target

    @classmethod
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, 'subject_type') and not inspect.isabstract(cls):
            raise TypeError(f"BaseGlueProxy subclass {cls.__name__} must define 'subject_type' attribute that matches the expected type of the __init__ 'target' parameter.")
        
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
    def from_proxy_registry_data(
        cls,
        access: GlueAccess,
        unique_name: str,
        **kwargs
    ) -> BaseGlueProxy:
        """
        Child proxy classes that require extra necessary logic to construct instances from raw data from the proxy registry can override this method.
        """
        return cls(
            access=access,
            unique_name=unique_name,
            **kwargs
        )

    def _build_session_data(self) -> dict:
        return {}

    def _build_context_data(self) -> dict:
        return {}

    def to_context_data(self):
        actions_data = {
            action_name: dict(action_parameters)
            for action_name, (_, action_parameters, _) in self.actions.items()
        }

        return dict(
            actions=actions_data
        ) | self._build_context_data()

    def to_session_data(self) -> dict:
        return dict(
            unique_name=self.unique_name,
            subject_type=self.subject_type.__name__,
            access=self.access
        ) | self._build_session_data()

    def process_action(
        self,
        action_data: dto.GlueActionRequestData
    ) -> dto.GlueActionResponseData:
        if not hasattr(self, action_data.action):
            raise TypeError(
                f"Instance of {type(self).__name__} must define '{action_data.action}' method to process this action.")

        if action_data.action not in self.actions:
            raise TypeError(
                f"Action method '{action_data.action}' must be decorated with '@action(access=GlueAccess.<REQUIRED_ACCESS>)' to specify required access.")

        action_func, action_parameters, required_access = self.actions[action_data.action]

        if not self.access.has_access(required_access):
            raise PermissionError(
                f"Insufficient access to perform '{action_data.action}' action.")

        if 'payload' not in action_parameters:
            if action_data.payload is not None:
                raise ValueError('This action does not support a payload parameter.')

            return action_func(self)
        else:
            return action_func(self, dict(**action_data.payload))

"""
Base proxy class for Django Glue.

This module provides the abstract base class that all proxy types inherit from,
defining the core interface for action registration, access control, and
session/context data serialization.
"""
from __future__ import annotations

import inspect
from abc import ABC
from typing import Any

from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue import data_transfer_objects as dto
from django_glue.data_transfer_objects import GlueActionRequestData
from django_glue.exceptions import GlueAccessError, GlueMissingActionError

from django_glue.session import GlueSession
from django_glue.utils import get_request_body_data


class BaseGlueProxy(ABC):
    """
    Abstract base class for all Django Glue proxies.

    Proxies act as intermediaries between Django backend objects (models, querysets,
    forms) and the JavaScript frontend. They expose actions that can be called from
    the client and enforce access control.

    Subclasses must define:
        _subject_type: The type of object this proxy wraps (e.g., Model, QuerySet).

    Attributes:
        unique_name: Identifier used to reference this proxy from JavaScript.
        access: The access level granted to the client (VIEW, CHANGE, or DELETE).
        target: The wrapped Django object.

    Example:
        class GlueModelProxy(BaseGlueProxy):
            _subject_type = Model

            @action(access=GlueAccess.VIEW)
            def get(self):
                return model_to_dict(self.target)
    """

    _subject_type: type
    _actions = {}

    def __init__(
        self,
        target: Any,
        unique_name: str,
        access: GlueAccess | str = GlueAccess.VIEW,
        **kwargs
    ):
        if not isinstance(target, self._subject_type):
            raise ValueError(
                f"The value passed to 'target' for {self.__class__} must be an instance of {self._subject_type.__name__} (according to the type assigned to '{self.__class__.__name__}.obj_class').")

        self.unique_name = unique_name

        if isinstance(access, GlueAccess):
            self.access = access
        else:
            self.access = GlueAccess(access)

        self.target = target

    @classmethod
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, '_subject_type') and not inspect.isabstract(cls):
            raise TypeError(f"BaseGlueProxy subclass {cls.__name__} must define '_subject_type' attribute that matches the expected type of the __init__ 'target' parameter.")

        cls._actions[cls.__name__] = {}

        # Walk the MRO in reverse order (excluding object) so that child class
        # actions override parent class actions with the same name
        for klass in reversed(cls.__mro__):
            if klass is object:
                continue

            for attr_name, attr_value in klass.__dict__.items():
                if hasattr(attr_value, '_required_glue_access'):
                    parameters = inspect.signature(attr_value).parameters
                    parameter_data = {}

                    for param_name, param_value in parameters.items():
                        if param_name in ['args', 'kwargs', 'self']:
                            continue
                        else:
                            parameter_data[param_name] = param_value.annotation

                    cls._actions[cls.__name__][attr_name] = (
                        attr_value,
                        parameter_data,
                        attr_value._required_glue_access
                    )

    @property
    def actions(self):
        """Return the registered actions for this proxy class."""
        return self._actions[self.__class__.__name__]

    @classmethod
    def process_request(
        cls,
        request: HttpRequest,
    ):
        from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE

        data = get_request_body_data(request)
        action_data = dto.GlueActionRequestData(**data)

        proxy_access = GlueSession(request).get_proxy_access(action_data.unique_name)

        proxy = SUBJECT_TYPE_TO_PROXY_TYPE[
            action_data.context_data['subject_type']].from_action_request_data(
            access=proxy_access,
            unique_name=action_data.unique_name,
            **action_data.context_data
        )

        return proxy.process_action(action_data)

    @classmethod
    def from_action_request_data(
        cls,
        access: GlueAccess,
        unique_name: str,
        **kwargs
    ) -> BaseGlueProxy:
        """
        Reconstruct a proxy instance from data sent to action_view.

        Called when processing an action request to recreate the proxy from
        data sent in a request the action_view. Subclasses can override this to handle additional
        reconstruction logic (e.g., fetching model instances from the database).

        Args:
            access: The access level for this proxy.
            unique_name: The unique identifier for this proxy.
            **kwargs: Additional data stored in the session registry.

        Returns:
            A new proxy instance configured with the provided data.
        """
        return cls(
            access=access,
            unique_name=unique_name,
            **kwargs
        )

    def _build_context_data(self) -> dict:
        return {}

    def to_context_data(self):
        actions_data = {
            action_name: dict(action_parameters)
            for action_name, (_, action_parameters, _) in self.actions.items()
        }

        return dict(
            actions=actions_data,
            subject_type = self._subject_type.__name__,
        ) | self._build_context_data()

    def process_action(
        self,
        action: str,
        action_data: dto.GlueActionRequestData
    ) -> dto.GlueActionResponseData:
        if not hasattr(self, action):
            raise GlueMissingActionError(
                action=action,
                proxy_name=self.unique_name,
                reason=f"Method '{action}' does not exist on {type(self).__name__}"
            )

        if action not in self.actions:
            raise GlueMissingActionError(
                action=action,
                proxy_name=self.unique_name,
                reason="Method must be decorated with '@action(access=GlueAccess.<REQUIRED_ACCESS>)'"
            )

        action_func, action_parameters, required_access = self.actions[action]

        if not self.access.has_access(required_access):
            raise GlueAccessError(
                action=action,
                required_access=required_access.name,
                current_access=self.access.name
            )

        if 'payload' not in action_parameters:
            if action_data.payload:
                raise ValueError('This action does not support a payload parameter.')

            return action_func(self)
        else:
            return action_func(self, action_data.payload)

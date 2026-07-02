"""
Base proxy class for Django Glue.

This module provides the abstract base class that all proxy types inherit from,
defining the core interface for action registration, access control, and
session/context data serialization.
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, Callable, TYPE_CHECKING

from django_glue.access.access import GlueAccess
from django_glue.exceptions import GlueAccessError, GlueMissingActionError
from django_glue.resolver.action.schemas import ActionPayloadSchema

if TYPE_CHECKING:
    from django.http import HttpRequest


BASE_ACTION_CATEGORY_NAME = 'base'


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
        self, target: Any, unique_name: str, access: GlueAccess | str = GlueAccess.VIEW, **kwargs
    ):
        if not isinstance(target, self._subject_type):
            raise ValueError(
                f"The value passed to 'target' for {self.__class__} must be an instance of {self._subject_type.__name__} (according to the type assigned to '{self.__class__.__name__}.obj_class')."
            )

        self.unique_name = unique_name

        if isinstance(access, GlueAccess):
            self.access = access
        else:
            self.access = GlueAccess(access)

        self.target = target

        self._register_subject_actions()

    @classmethod
    def _register_actions(cls, subject_type: type, category: str | None = None):
        if cls.__name__ not in cls._actions:
            cls._actions[cls.__name__] = {}

        if category is None:
            category = BASE_ACTION_CATEGORY_NAME

        if category not in cls._actions[cls.__name__]:
            cls._actions[cls.__name__][category] = {}

        # First pass: collect all decorated action names and their access levels from the MRO
        # This allows child classes to inherit @action decoration from parent classes
        decorated_actions = {}
        for klass in reversed(subject_type.__mro__):
            if klass is object:
                continue
            for attr_name, attr_value in klass.__dict__.items():
                if hasattr(attr_value, '_required_glue_access'):
                    decorated_actions[attr_name] = attr_value._required_glue_access

        # Second pass: register the actual implementation (may be overridden in child class)
        # using the access level from the decorated parent
        for attr_name, required_access in decorated_actions.items():
            # Get the actual method implementation (resolves to child's override if exists)
            actual_method = getattr(subject_type, attr_name)

            parameters = inspect.signature(actual_method).parameters
            parameter_data = {}

            # Skip internal params that are handled by _build_action_kwargs
            internal_params = {'self', 'args', 'kwargs', 'request', 'user_data', 'file_data', 'context_data'}
            first_param_seen = False

            for param_name, param_value in parameters.items():
                if param_name == 'self':
                    continue

                # Skip first param after self (always 'request')
                if not first_param_seen:
                    first_param_seen = True
                    continue

                # Skip other internal params
                if param_name in internal_params:
                    continue

                # Convert annotation to string for JSON serialization
                annotation = param_value.annotation
                if annotation is inspect.Parameter.empty:
                    parameter_data[param_name] = None
                elif isinstance(annotation, type):
                    parameter_data[param_name] = annotation.__name__
                else:
                    parameter_data[param_name] = str(annotation)

            cls._actions[cls.__name__][category][attr_name] = (
                actual_method,
                parameter_data,
                required_access,
            )

    @classmethod
    def __init_subclass__(cls, **kwargs):
        is_abstract = inspect.isabstract(cls)
        if not hasattr(cls, '_subject_type') and not is_abstract:
            raise TypeError(
                f"BaseGlueProxy subclass {cls.__name__} must define '_subject_type' attribute that matches the expected type of the __init__ 'target' parameter."
            )

        cls._register_actions(subject_type=cls, category=BASE_ACTION_CATEGORY_NAME)

    def _register_subject_actions(self):
        pass

    def _get_subject_action_target_by_category(
        self,
        category: str,
        action_payload: ActionPayloadSchema
    ) -> Any:
        return None

    @property
    def actions(self) -> dict:
        """Return the registered actions for this proxy class and its subject actions."""
        return self._actions[self.__class__.__name__]

    @classmethod
    def from_action_request_data(
        cls, access: GlueAccess, unique_name: str, **kwargs
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
        return cls(access=access, unique_name=unique_name, **kwargs)

    def _build_context_data(self) -> dict:
        return {}

    def to_context_data(self):
        actions_data = {}
        for action_category in self.actions.keys():
            actions_data.update({
                action_name: dict(action_parameters)
                for action_name, (_, action_parameters, _) in
                self.actions[action_category].items()
            })

        # make sure the context_data is always sorted the same for security checksums
        return dict(sorted(
            dict(
                actions=actions_data,
                subject_type=self._subject_type.__name__,
                **self._build_context_data()
            ).items()
        ))

    def _build_action_kwargs(
        self,
        action_func: Callable,
        action_payload: ActionPayloadSchema,
        request: HttpRequest | None
    ) -> dict:
        """
        Build kwargs for action based on its signature.

        - First param after 'self' always receives request
        - 'user_data' param receives the full user_data dict (action-specific data from user)
        - 'proxy_data' param receives the full proxy_data dict (proxy-intrinsic state)
        - 'file_data' param receives the full file_data dict
        - 'context_data' param receives the full context_data dict
        - Other params are extracted from user_data by name
        """
        sig = inspect.signature(action_func)
        kwargs = {}
        user_data = action_payload.user_data or {}
        proxy_data = action_payload.proxy_data or {}
        file_data = action_payload.file_data or {}
        context_data = action_payload.context_data or {}

        params = list(sig.parameters.items())
        first_param_handled = False

        for param_name, param in params:
            if param_name == 'self':
                continue

            # First param after self always gets request
            if not first_param_handled:
                first_param_handled = True
                kwargs[param_name] = request
                continue

            # Special params for full dicts
            if param_name == 'user_data':
                kwargs[param_name] = user_data
            elif param_name == 'proxy_data':
                kwargs[param_name] = proxy_data
            elif param_name == 'file_data':
                kwargs[param_name] = file_data
            elif param_name == 'context_data':
                kwargs[param_name] = context_data
            # Regular params come from user_data by name
            elif param_name in user_data:
                kwargs[param_name] = user_data[param_name]
            elif param.default is not inspect.Parameter.empty:
                # Has default, skip (will use default)
                pass
            # else: missing required param - let Python raise TypeError

        return kwargs

    def process_action(
        self,
        action: str,
        action_payload: ActionPayloadSchema,
        request: HttpRequest | None = None
    ) -> dict:
        for category, category_actions in self.actions.items():
            if action in category_actions:
                action_func, _, required_access = category_actions[action]
                if category == BASE_ACTION_CATEGORY_NAME:
                    action_target = self
                else:
                    action_target = self._get_subject_action_target_by_category(
                        category=category,
                        action_payload=action_payload
                    )

                # Store for get_response_proxy_data to access
                self._last_action_target = action_target
                self._last_action_category = category

                if not self.access.has_access(required_access):
                    raise GlueAccessError(
                        action=action,
                        required_access=required_access.name,
                        current_access=self.access.name
                    )

                kwargs = self._build_action_kwargs(
                    action_func=action_func,
                    action_payload=action_payload,
                    request=request
                )

                return action_func(action_target, **kwargs)

        raise GlueMissingActionError(
            action=action,
            proxy_name=self.unique_name,
            reason=(
                "No valid action candidate was found for the {self.__class__.__name__}"
                " proxy for subject type {self._subject_type.__name__}."
                " A method must be defined either directly on the proxy class, or the "
                " proxy's subject class, and it must be decorated with"
                " '@action(access=GlueAccess.<REQUIRED_ACCESS>)'"
            )
        )

    def get_response_proxy_data(
        self,
        action: str,
        action_payload: ActionPayloadSchema
    ) -> dict | None:
        """
        Get proxy-intrinsic data to include in the response.

        Override in subclasses to include proxy-specific state like form errors.
        This is the response counterpart to proxy_data in the request.

        Returns:
            dict with proxy-intrinsic state, or None if no data to send.
        """
        return None

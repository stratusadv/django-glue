"""
Base proxy class for Django Glue.

This module provides the abstract base class that all proxy types inherit from,
defining the core interface for action registration, access control, and
session/context data serialization.
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, Callable, TYPE_CHECKING, Generic, Self, TypeVar, get_type_hints

from pydantic import BaseModel, TypeAdapter, ValidationError
from django.http import HttpRequest

from django_glue.access.access import GlueAccess
from django_glue.actions import GlueAction
from django_glue.proxies.contract import GlueProxyContract
from django_glue.exceptions import GlueAccessError
from django_glue.response import ActionResult

if TYPE_CHECKING:
    from django_glue.resolver.action.schemas import ActionRequest


BASE_ACTION_CATEGORY_NAME = 'base'

TContract = TypeVar('TContract', bound=GlueProxyContract)


class BaseGlueProxy(ABC, Generic[TContract]):
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
    _actions: dict[str, GlueAction] = {}

    def __init__(
        self,
        name: str,
        namespace: str,
        access: GlueAccess,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.access = access
        self.access = access
        self._register_actions_for_class(target_class=self.__class__)

    # TODO: Override this to define how the proxy subject
    # is constructed from the action_request object
    @classmethod
    def _from_action_request(cls, action_request: ActionRequest) -> Self:
        raise NotImplementedError

    @classmethod
    def _register_actions_for_class(
        cls,
        target_class: type,
    ) -> None:
        # First pass: collect all decorated action names and their access levels from the MRO
        # This allows child classes to inherit @action decoration from parent classes
        decorated_actions = {}
        for klass in reversed(target_class.__mro__):
            if klass is object:
                continue
            for attr_name, attr_value in klass.__dict__.items():
                if hasattr(attr_value, '_required_glue_access'):
                    decorated_actions[attr_name] = attr_value._required_glue_access

        # Second pass: register the actual implementation (may be overridden in child class)
        # using the access level from the decorated parent
        for attr_name, required_access in decorated_actions.items():
            # Get the actual method implementation (resolves to child's override if exists)
            actual_method = getattr(target_class, attr_name)

            parameters = inspect.signature(actual_method).parameters
            parameter_data: dict[str, str | None] = {}

            for param_name, param_value in list(parameters.items())[2:]:
                # Convert annotation to string for JSON serialization
                annotation = param_value.annotation
                if annotation is inspect.Parameter.empty:
                    parameter_data[param_name] = None
                elif isinstance(annotation, type):
                    parameter_data[param_name] = annotation.__name__
                else:
                    parameter_data[param_name] = str(annotation)

            cls._actions[attr_name] = GlueAction(
                name=attr_name,
                parameters=parameter_data,
                required_access=required_access,
                target_class_path=f'{target_class.__module__}.{target_class.__name__}'
            )

    @classmethod
    def __init_subclass__(cls, **kwargs):
        is_abstract = inspect.isabstract(cls)
        if not hasattr(cls, '_subject_type') and not is_abstract:
            msg = (
                f"BaseGlueProxy subclass {cls.__name__} must define '_subject_type "
                "attribute that matches the expected type of the __init__ 'target' parameter."
            )
            raise TypeError(msg)

    def _get_external_target_for_action_request(
        self,
        action_request: ActionRequest
    ) -> tuple[GlueAction, Any]:
        raise NotImplementedError

    @property
    def state(self) -> BaseModel | None:
        return None

    @property
    def _custom_contract_data(self) -> dict:
        return {}

    @property
    def _action_contract_data(self) -> dict:
        return {
            action_name: action.model_dump()
            for action_name, action in self._actions.items()
        }

    def register_with_request(self, request: HttpRequest) -> None:
        request_proxy_contracts = request.__dict__['__glue_proxy_contracts__']

        if not request_proxy_contracts:
            request_proxy_contracts = {}

        request_proxy_contracts[self] = GlueProxyContract.initialize({
            'name': self.name,
            'namespace': self.namespace,
            'access': self.access,
            'subject_type': self._subject_type.__name__,
            'actions': self._action_contract_data,
            'custom_data': self._custom_contract_data
        }).model_dump()

    def _build_action_kwargs(
        self,
        action_callable: Callable,
        action_request: ActionRequest,
    ) -> dict:
        unwrapped_func = inspect.unwrap(action_callable)
        sig = inspect.signature(unwrapped_func)

        # Safely resolve string annotations (e.g., from __future__ import annotations)
        type_hints = get_type_hints(unwrapped_func)

        kwargs = {}
        action_kwargs = action_request.action_kwargs or {}
        params = list(sig.parameters.items())

        # Handle request param
        request_param_name, _ = params[1]
        kwargs[request_param_name] = action_request.request

        for param_name, param in params[2:]:
            if param_name in action_kwargs:
                raw_value = action_kwargs[param_name]

                # Check if we have a type hint for this parameter
                if param_name in type_hints:
                    annotation = type_hints[param_name]
                    try:
                        # TypeAdapter validates and optionally coerces the data
                        validator = TypeAdapter(annotation)
                        kwargs[param_name] = validator.validate_python(raw_value)
                    except ValidationError as e:
                        # Surface a clean error pointing out exactly which param failed
                        msg = f"Validation failed for param '{param_name}': {e}"
                        raise TypeError(msg) from e
                else:
                    # No type hint provided, just pass the value
                    kwargs[param_name] = raw_value

            elif param.default is not inspect.Parameter.empty:
                pass

        return kwargs

    @classmethod
    def process_action_request(
        cls,
        action_request: ActionRequest,
        **kwargs
    ) -> ActionResult:
        instance = cls._from_action_request(action_request=action_request)

        action = cls._actions[action_request.action_name]

        if issubclass(action.target_class, cls):
            # the action targets the proxy instance itself
            action_target = instance
        else:
            # the action targets something external (e.g. a model class, queryset class)
            # subclasses with override the below method to define custom logic for building
            # externally typed targets
            action_target = instance._get_external_target_for_action_request(
                action_request=action_request
            )

        if not instance.access.has_access(action.required_access):
            raise GlueAccessError(
                action=action.name,
                required_access=action.required_access,
                current_access=instance.access
            )

        action_callable = action.callable

        action_kwargs = instance._build_action_kwargs(
            action_callable=action_callable,
            action_request=action_request,
        )

        action_result_data = action_callable(action_target, **action_kwargs)

        return ActionResult(
            proxy_state=instance.state,
            payload=action_result_data,
        )

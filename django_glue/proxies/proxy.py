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
from django_glue.actions.decorators import GLUE_ACTIONS
from django_glue.constants import DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY
from django_glue.proxies.contract import GlueProxyContract
from django_glue.exceptions import GlueAccessError
from django_glue.response import ActionResult

if TYPE_CHECKING:
    from django_glue.actions.action import GlueAction
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

    def __init__(
        self,
        name: str,
        namespace: str,
        access: GlueAccess,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.access = access

    # TODO: Override this to define how the proxy subject
    # is constructed from the action_request object
    @classmethod
    def _from_action_request(cls, action_request: ActionRequest) -> Self:
        raise NotImplementedError

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        is_abstract = inspect.isabstract(cls)
        if not hasattr(cls, '_subject_type') and not is_abstract:
            msg = (
                f"BaseGlueProxy subclass {cls.__name__} must define '_subject_type "
                "attribute that matches the expected type of the __init__ 'target' parameter."
            )
            raise TypeError(msg)

    @property
    def primary_subject(self) -> Any:
        raise NotImplementedError

    def _get_action_target(
        self,
        action: GlueAction,
    ) -> Any:
        if issubclass(action.target_class, self.__class__):
            return self

        return None

    def get_state(self) -> BaseModel | None:
        return None

    @property
    def _custom_contract_data(self) -> dict:
        return {}

    @property
    def _action_contract_data(self) -> dict:
        action_data = {
            action_name: action.model_dump(exclude={'provider_factory'}, exclude_none=True)
            for action_name, action in GLUE_ACTIONS.items()
            if self._get_action_target(action) is not None
        }

        return action_data

    def register_with_request(self, request: HttpRequest) -> None:
        if DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY not in request.__dict__:
            request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY] = {}

        request.__dict__[DJANGO_GLUE_PROXIES_REQUEST_ATTR_KEY][self.name] = {
            'state': {},
            'contract': GlueProxyContract.initialize({
                'name': self.name,
                'namespace': self.namespace,
                'access': self.access,
                'subject_type': self._subject_type.__name__,
                'actions': self._action_contract_data,
                'custom_data': self._custom_contract_data
            }).model_dump(),
        }

    def _build_action_kwargs(
        self,
        action_callable: Callable,
        action_request: ActionRequest,
    ) -> dict:
        unwrapped_func = inspect.unwrap(action_callable)
        sig = inspect.signature(unwrapped_func)

        # Safely resolve string annotations (e.g., from __future__ import annotations)
        type_hints = get_type_hints(unwrapped_func, globalns={'HttpRequest': HttpRequest})

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

        action: GlueAction = GLUE_ACTIONS[action_request.action_name]

        if not instance.access.has_access(action.required_access):
            raise GlueAccessError(
                action=action.name,
                required_access=action.required_access,
                current_access=instance.access
            )

        action_target = instance._get_action_target(action)
        if not action_target:
            raise ValueError(f'No valid action target was found for {action.target_class.__class__.__name__}')

        # If action has a provider factory, that means the target must be updated to be an instance
        # the action provider constructed using the original action target.
        if action.provider_factory is not None:
            action_target = action.provider_factory(action_target)

        action_callable = action.callable

        action_kwargs = instance._build_action_kwargs(
            action_callable=action_callable,
            action_request=action_request,
        )

        action_result_data = action_callable(action_target, **action_kwargs)

        return ActionResult(
            state=instance.get_state(), # send fresh, updated state after the action was run
            payload=action_result_data,
        )

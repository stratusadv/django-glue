"""
Custom exceptions for Django Glue.

These exceptions provide clear, specific error types for different failure modes,
making it easier to handle errors appropriately in views and client code.
"""

from typing import Any


class GlueError(Exception):
    """Base exception for all Django Glue errors."""


class GlueProxyNotFoundError(GlueError):
    """Raised when a proxy with the given unique_name is not found in the session."""

    def __init__(self, unique_name: str) -> None:
        self.unique_name = unique_name
        super().__init__(f"Proxy '{unique_name}' not found in session.")


class GlueAccessError(GlueError):
    """Raised when a user lacks permission to access a bound attribute on a proxy."""

    def __init__(self, attribute: str, required_access: str, current_access: str) -> None:
        self.attribute = attribute
        self.required_access = required_access
        self.current_access = current_access
        super().__init__(
            f"Insufficient access to access '{attribute}'. "
            f'Required: {required_access}, Current: {current_access}'
        )


class GlueMissingAttributeError(GlueError):
    """Raised when a requested bound attribute does not exist or is not properly exposed."""

    def __init__(self, attribute: str, proxy_name: str, reason: str | None = None) -> None:
        self.attribute = attribute
        self.proxy_name = proxy_name
        self.reason = reason
        message = f"Attribute '{attribute}' not found on proxy '{proxy_name}'"
        if reason:
            message += f': {reason}'
        super().__init__(message)


class GlueModelInstanceNotFoundError(GlueError):
    """Raised when a model instance is not found during proxy operations (get, save, delete)."""

    def __init__(self, model_name: str, pk: Any) -> None:
        self.model_name = model_name
        self.pk = pk
        super().__init__(f'{model_name} with pk={pk} does not exist.')


class GlueQuerySetFilterValidationError(GlueError):
    """Raised when filter parameters reference disallowed fields."""

    def __init__(self, field: str, allowed_fields: list) -> None:
        self.field = field
        self.allowed_fields = allowed_fields
        super().__init__(f"Cannot filter on field '{field}'. Allowed fields: {allowed_fields}")


class GlueInvalidPolicyError(GlueError):
    """Raised when proxy policy signature doesn't match, indicating tampering."""

    def __init__(self, unique_name: str) -> None:
        self.unique_name = unique_name
        super().__init__(
            f"Policy for proxy '{unique_name}' is invalid. "
            "The signature does not match - the data may have been tampered with."
        )


class GlueBoundAttributeCallError(GlueError):
    """Raised when calling a bound attribute fails. Provides detailed context about the failure."""

    def __init__(self, callable_attr: Any, original_error: Exception, provided_kwargs: list[str]) -> None:
        import inspect
        self.original_error = original_error
        self.provided_kwargs = provided_kwargs

        # Get the unwrapped function for better error messages
        unwrapped = inspect.unwrap(callable_attr)
        self.func_name = f'{unwrapped.__module__}.{unwrapped.__qualname__}'

        # Get expected parameters
        sig = inspect.signature(unwrapped)
        self.expected_params = [
            name for name, param in sig.parameters.items()
            if name != 'self'
        ]

        super().__init__(
            f'{self.func_name}() failed: {original_error}. '
            f'Expected params: {self.expected_params}, '
            f'Provided kwargs: {provided_kwargs}'
        )

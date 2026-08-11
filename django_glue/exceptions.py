"""
Custom exceptions for Django Glue.

These exceptions provide clear, specific error types for different failure modes,
making it easier to handle errors appropriately in views and client code.
"""

import inspect
from enum import StrEnum
from typing import Any


class GlueRequestErrorCode(StrEnum):
    """Error codes for malformed or invalid Glue requests."""

    # Content/format errors
    INVALID_CONTENT_TYPE = 'invalid_content_type'
    INVALID_JSON = 'invalid_json'
    INVALID_KWARGS = 'invalid_kwargs'

    # Missing required fields
    MISSING_FIELD = 'missing_field'

    # Path/body mismatch errors
    OBJECT_NAME_MISMATCH = 'object_name_mismatch'
    ATTRIBUTE_NAME_MISMATCH = 'attribute_name_mismatch'
    MISSING_PATH_PARAMETERS = 'missing_path_parameters'

    # Pydantic validation
    MALFORMED_REQUEST = 'malformed_request'

    # View fragment request errors
    MISSING_VIEW_TARGET = 'missing_view_target'
    VIEW_URL_NAME_NOT_FOUND = 'view_url_name_not_found'
    VIEW_URL_PATH_NOT_FOUND = 'view_url_path_not_found'
    VIEW_REDIRECT_URL_NOT_FOUND = 'view_redirect_url_not_found'
    EXTERNAL_VIEW_REDIRECT_NOT_SUPPORTED = 'external_view_redirect_not_supported'
    TOO_MANY_VIEW_REDIRECTS = 'too_many_view_redirects'
    UNSUPPORTED_VIEW_RESPONSE_TYPE = 'unsupported_view_response_type'
    VIEW_CALL_FAILED = 'view_call_failed'


class GlueError(Exception):
    """Base exception for all Django Glue errors."""

    code = 'glue_error'
    status = 500

    def details(self) -> dict:
        return {}


class GlueRequestError(GlueError):
    """Raised when a Glue request is malformed or internally inconsistent."""

    status = 400

    def __init__(
        self,
        code: GlueRequestErrorCode | str,
        message: str,
        details: dict | None = None,
        status: int | None = None,
    ) -> None:
        self.code = str(code)
        self._details = details or {}
        if status is not None:
            self.status = status
        super().__init__(message)

    def details(self) -> dict:
        return self._details


class GlueAccessError(GlueError):
    """Raised when a user lacks permission to access a bound attribute on a proxy."""

    code = 'proxy_access_denied'
    status = 403

    def __init__(self, attribute: str, required_access: str, current_access: str) -> None:
        self.attribute = attribute
        self.required_access = required_access
        self.current_access = current_access
        super().__init__(
            f"Insufficient access to access '{attribute}'. "
            f'Required: {required_access}, Current: {current_access}'
        )

    def details(self) -> dict:
        return {
            'attribute': self.attribute,
            'required_access': self.required_access,
            'current_access': self.current_access,
        }


class GlueMissingAttributeError(GlueError):
    """Raised when a requested bound attribute does not exist or is not properly exposed."""

    code = 'missing_attribute'
    status = 404

    def __init__(self, attribute: str, proxy_name: str, reason: str | None = None) -> None:
        self.attribute = attribute
        self.proxy_name = proxy_name
        self.reason = reason
        message = f"Attribute '{attribute}' not found on proxy '{proxy_name}'"
        if reason:
            message += f': {reason}'
        super().__init__(message)

    def details(self) -> dict:
        details = {
            'attribute': self.attribute,
            'proxy': self.proxy_name,
        }
        if self.reason:
            details['reason'] = self.reason
        return details


class GlueInvalidAttributeError(GlueError):
    """Raised when a declared Glue attribute cannot be exposed safely."""

    code = 'invalid_attribute_configuration'
    status = 500

    def __init__(
        self,
        attribute: str,
        owner: str,
        value_type: str,
    ) -> None:
        self.attribute = attribute
        self.owner = owner
        self.value_type = value_type
        super().__init__(
            f"Attribute '{attribute}' on '{owner}' was declared with Glue.attribute(...), "
            f"but its value '{value_type}' is neither JSON-serializable state nor a "
            'container with nested Glue attributes. '
            f"To expose nested attributes inside '{owner}.{attribute}', wrap/decorate "
            'the nested attributes with Glue.attribute(...).'
        )

    def details(self) -> dict:
        return {
            'attribute': self.attribute,
            'owner': self.owner,
            'value_type': self.value_type,
        }


class GlueModelInstanceNotFoundError(GlueError):
    """Raised when a model instance is not found during proxy operations (get, save, delete)."""

    code = 'model_instance_not_found'
    status = 404

    def __init__(self, model_name: str, pk: Any) -> None:
        self.model_name = model_name
        self.pk = pk
        super().__init__(f'{model_name} with pk={pk} does not exist.')

    def details(self) -> dict:
        return {
            'model': self.model_name,
            'pk': self.pk,
        }


class GlueQuerySetFilterValidationError(GlueError):
    """Raised when filter parameters reference disallowed fields."""

    code = 'queryset_filter_validation_error'
    status = 422

    def __init__(self, field: str, allowed_fields: list) -> None:
        self.field = field
        self.allowed_fields = allowed_fields
        super().__init__(f"Cannot filter on field '{field}'. Allowed fields: {allowed_fields}")

    def details(self) -> dict:
        return {
            'field': self.field,
            'allowed_fields': self.allowed_fields,
        }


class GlueInvalidPolicyError(GlueError):
    """Raised when proxy policy signature doesn't match, indicating tampering."""

    code = 'proxy_policy_invalid'
    status = 403

    def __init__(self, unique_name: str) -> None:
        self.unique_name = unique_name
        super().__init__(
            f"Policy for proxy '{unique_name}' is invalid. "
            "The signature does not match - the data may have been tampered with."
        )

    def details(self) -> dict:
        return {'proxy': self.unique_name}


class GlueInvalidSessionError(GlueError):
    """Raised when the policy's session_id doesn't match the current request session."""

    code = 'proxy_invalid_session'
    status = 403

    def __init__(
        self,
        unique_name: str,
        *,
        policy_session_id: str | None = None,
        current_session_id: str | None = None,
    ) -> None:
        self.unique_name = unique_name
        self.policy_session_id = policy_session_id
        self.current_session_id = current_session_id
        super().__init__(
            f"Policy for proxy '{unique_name}' is not valid for the current session."
        )

    def details(self) -> dict:
        return {
            'proxy': self.unique_name,
            'policy_session_id': self.policy_session_id,
            'current_session_id': self.current_session_id,
        }


class GlueInvalidUserError(GlueError):
    """Raised when a policy was issued for a different authenticated user."""

    code = 'proxy_invalid_user'
    status = 403

    def __init__(
        self,
        unique_name: str,
        *,
        policy_user_id: Any = None,
        current_user_id: Any = None,
    ) -> None:
        self.unique_name = unique_name
        self.policy_user_id = policy_user_id
        self.current_user_id = current_user_id
        super().__init__(
            f"Policy for proxy '{unique_name}' is not valid for the current user."
        )

    def details(self) -> dict:
        return {
            'proxy': self.unique_name,
            'policy_user_id': self.policy_user_id,
            'current_user_id': self.current_user_id,
        }


class GlueExpiredPolicyError(GlueError):
    """Raised when a proxy policy is older than the configured max age."""

    code = 'proxy_policy_expired'
    status = 419

    def __init__(self, unique_name: str) -> None:
        self.unique_name = unique_name
        super().__init__(f"Policy for proxy '{unique_name}' has expired.")

    def details(self) -> dict:
        return {'proxy': self.unique_name}


class GlueCalledStateAttributeError(GlueError):
    code = 'called_state_attribute'
    status = 404

    def __init__(self, attribute: str, proxy_name: str, reason: str | None = None) -> None:
        self.attribute = attribute
        self.proxy_name = proxy_name
        self.reason = reason
        message = (
            f"Invalid attribute target {attribute}. Only CallableAttributes can be called."
        )
        if reason:
            message += f': {reason}'
        super().__init__(message)

    def details(self) -> dict:
        details = {
            'attribute': self.attribute,
            'proxy': self.proxy_name,
        }
        if self.reason:
            details['reason'] = self.reason
        return details

class GlueAttributeCallError(GlueError):
    """Raised when calling a bound attribute fails. Provides detailed context about the failure."""

    code = 'bound_attribute_call_error'
    status = 500

    def __init__(
        self,
        callable_attr: Any,
        original_error: Exception,
        provided_kwargs: list[str],
    ) -> None:
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

    def details(self) -> dict:
        return {
            'function': self.func_name,
            'expected_params': self.expected_params,
            'provided_kwargs': self.provided_kwargs,
            'original_error': str(self.original_error),
        }

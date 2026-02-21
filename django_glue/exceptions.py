"""
/Custom exceptions for Django Glue.

These exceptions provide clear, specific error types for different failure modes,
making it easier to handle errors appropriately in views and client code.
"""


class GlueError(Exception):
    """Base exception for all Django Glue errors."""
    pass


class GlueProxyNotFoundError(GlueError):
    """Raised when a proxy with the given unique_name is not found in the session."""

    def __init__(self, unique_name: str):
        self.unique_name = unique_name
        super().__init__(f"Proxy '{unique_name}' not found in session.")


class GlueAccessError(GlueError):
    """Raised when a user lacks permission to perform an action on a proxy."""

    def __init__(self, action: str, required_access: str, current_access: str):
        self.action = action
        self.required_access = required_access
        self.current_access = current_access
        super().__init__(
            f"Insufficient access to perform '{action}'. "
            f"Required: {required_access}, Current: {current_access}"
        )


class GlueMissingActionError(GlueError):
    """Raised when a called action method does not exist or is not properly decorated."""

    def __init__(self, action: str, proxy_name: str, reason: str = None):
        self.action = action
        self.proxy_name = proxy_name
        self.reason = reason
        message = f"Action '{action}' not found on proxy '{proxy_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class GlueModelInstanceNotFoundError(GlueError):
    """Raised when a model instance is not found during proxy operations (get, save, delete)."""

    def __init__(self, model_name: str, pk: any):
        self.model_name = model_name
        self.pk = pk
        super().__init__(f"{model_name} with pk={pk} does not exist.")


class GlueQuerySetFilterValidationError(GlueError):
    """Raised when filter parameters reference disallowed fields."""

    def __init__(self, field: str, allowed_fields: list):
        self.field = field
        self.allowed_fields = allowed_fields
        super().__init__(
            f"Cannot filter on field '{field}'. "
            f"Allowed fields: {allowed_fields}"
        )

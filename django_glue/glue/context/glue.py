from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from django_glue.access.access import Access
from django_glue.glue.context.response_data import ContextGlueJsonData
from django_glue.glue.context.serializers import serialize_context
from django_glue.glue.context.session_data import ContextGlueSessionData
from django_glue.glue.enums import GlueType
from django_glue.glue.glue import BaseGlue

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class ContextGlue(BaseGlue):
    def __init__(
        self,
        unique_name: str,
        context_data: dict[str, Any],
        user: User | None = None,
        permission_checker: Callable | None = None,
        access: Access | str = Access.VIEW,
        exclude: list[str] | set[str] | tuple | None = None
    ):
        self.permission_checker = permission_checker
        self.user = user

        super().__init__(unique_name, GlueType.CONTEXT, access)

        self._original_data = context_data
        self.exclude = exclude or []

        self.context_data = serialize_context(
            context_data,
            user=self.user,
            permission_checker=self.permission_checker,
            exclude=self.exclude,
            max_depth=10
        )

    def get_context(self) -> dict[str, Any]:
        return self.context_data

    def to_session_data(self) -> ContextGlueSessionData:
        user_id = self.user.id if self.user and hasattr(self.user, 'id') else None

        return ContextGlueSessionData(
            unique_name=self.unique_name,
            glue_type=self.glue_type,
            access=self.access,
            context_data=self.context_data,
            exclude=self.exclude,
            user_id=user_id
        )

    def to_response_data(self) -> ContextGlueJsonData:
        return ContextGlueJsonData(self.context_data)

from __future__ import annotations

from enum import StrEnum
from typing import Any


class GlueAccess(StrEnum):
    # The order of these variables controls how the permission cascade each other in the has_access method
    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'

    def __str__(self) -> str:
        return self.value

    def has_access(self, access_required: GlueAccess) -> bool:
        access_tuple = tuple(GlueAccess.__members__.values())
        return access_tuple.index(self) >= access_tuple.index(access_required)

    @staticmethod
    def required_save_access(glue: Any) -> GlueAccess:
        """The access a save of ``glue``'s target requires (ADR 009, ADR 018):
        ADD while the model instance is unsaved, including a form without an
        instance, and CHANGE once it is persisted. Pass it as a callable
        ``required_access`` so one method can both create and update without
        letting a create-only object modify a persisted row."""
        instance = getattr(glue, 'instance', None)
        if instance is None:
            instance = getattr(getattr(glue, 'form', None), 'instance', None)
        if instance is None or instance.pk is None:
            return GlueAccess.ADD
        return GlueAccess.CHANGE

from __future__ import annotations

from enum import Enum


class GlueAccess(str, Enum):
    # The order of these variables controls how the permission cascade each other in the has_access method
    VIEW = 'view'
    CHANGE = 'change'
    DELETE = 'delete'

    def __str__(self):
        return self.value

    def has_access(self, access_required: GlueAccess):
        glue_access_tuple = tuple(GlueAccess.__members__.values())
        if glue_access_tuple.index(self) >= glue_access_tuple.index(access_required):
            return True
        else:
            return False


from __future__ import annotations

from enum import Enum


class Access(str, Enum):
    # The order of these variables controls how the permission cascade each other in the has_access method
    VIEW = 'view'
    CHANGE = 'change'
    DELETE = 'delete'

    def __str__(self) -> str:
        return self.value

    def has_access(self, access_required: Access) -> bool:
        access_tuple = tuple(Access.__members__.values())

        if access_tuple.index(self) >= access_tuple.index(access_required):
            return True

        return False


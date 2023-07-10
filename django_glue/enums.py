from __future__ import annotations

from enum import Enum


class GlueAccess(str, Enum):
    # The order of these variables controls how the permission cascade each other in the has_access method
    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'
    ADMIN = 'admin'

    def __str__(self):
        return self.value

    def has_access(self, access_required: GlueAccess):
        glue_access_tuple = tuple(GlueAccess.__members__.values())
        if glue_access_tuple.index(self) >= glue_access_tuple.index(access_required):
            return True
        else:
            return False


class GlueAction(str, Enum):
    GET = 'get'
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    METHOD = 'method'

    def __str__(self):
        return self.value

    @property
    def required_access(self) -> GlueAccess:
        if self.value == 'get':
            return GlueAccess.VIEW
        elif self.value == 'create':
            return GlueAccess.ADD
        elif self.value == 'update':
            return GlueAccess.CHANGE
        elif self.value == 'delete':
            return GlueAccess.DELETE
        elif self.value == 'method':
            return GlueAccess.VIEW


class GlueConnection(str, Enum):
    MODEL_OBJECT = 'model_object'
    QUERY_SET = 'query_set'
    TEMPLATE = 'template'

    def __str__(self):
        return self.value


class GlueJsonResponseType(str, Enum):
    SUCCESS = 'success'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    DEBUG = 'debug'

    def __str__(self):
        return self.value


class GlueJsonResponseStatus(str, Enum):
    SUCCESS = '200'
    SILENT_SUCCESS = '204'
    ERROR = '404'

    def __str__(self):
        return self.value


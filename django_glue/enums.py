from enum import Enum


class GlueAccess(str, Enum):
    VIEW = 'view'
    ADD = 'add'
    CHANGE = 'change'
    DELETE = 'delete'

    def __str__(self):
        return self.value

class GlueConnection(str, Enum):
    MODEL_OBJECT = 'model_object'
    QUERY_SET = 'query_set'

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


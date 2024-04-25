from enum import Enum


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


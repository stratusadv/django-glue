from enum import Enum
from django.contrib.messages import constants


class MessageLevel(Enum):
    DEBUG = constants.DEBUG
    INFO = constants.INFO
    SUCCESS = constants.SUCCESS
    WARNING = constants.WARNING
    ERROR = constants.ERROR

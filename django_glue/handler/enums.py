from enum import Enum


class GlueConnection(str, Enum):
    MODEL_OBJECT = 'model_object'
    QUERY_SET = 'query_set'
    TEMPLATE = 'template'
    FUNCTION = 'function'

    def __str__(self):
        return self.value



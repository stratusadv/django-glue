from enum import Enum


class GlueType(str, Enum):
    MODEL_OBJECT = 'model_object'
    QUERY_SET = 'query_set'
    TEMPLATE = 'template'
    FUNCTION = 'function'
    CONTEXT = 'context'

    def __str__(self) -> str:
        return self.value



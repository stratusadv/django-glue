from enum import Enum


class FieldTypes(str, Enum):
    """
        Value represents the string how django names their field types
    """
    BOOLEAN = 'Boolean'
    CHAR_FIELD = 'Character Field'

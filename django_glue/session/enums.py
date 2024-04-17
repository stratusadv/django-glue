from enum import Enum


class GlueSessionTypes(str, Enum):
    CONTEXT = 'context'
    META = 'meta'

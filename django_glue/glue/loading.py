from enum import StrEnum


class LoadingStrategy(StrEnum):
    LAZY = 'lazy'
    EAGER = 'eager'
    INHERIT = 'inherit'

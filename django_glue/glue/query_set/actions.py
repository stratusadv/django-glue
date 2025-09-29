from django_glue.access.access import Access
from django_glue.access.actions import BaseGlueActionType


class QuerySetGlueActionType(BaseGlueActionType):
    ALL = 'all'
    FILTER = 'filter'
    GET = 'get'
    UPDATE = 'update'
    DELETE = 'delete'
    METHOD = 'method'
    NULL_OBJECT = 'null_object'
    TO_CHOICES = 'to_choices'

    def required_access(self) -> Access:
        if self.value in ['get', 'all', 'filter', 'null_object', 'to_choices']:
            return Access.VIEW
        elif self.value in ['update', 'method']:
            return Access.CHANGE
        elif self.value == 'delete':
            return Access.DELETE
        else:
            raise ValueError('That is not a valid action on a glue query set.')

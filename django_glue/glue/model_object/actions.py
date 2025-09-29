from django_glue.access.access import Access
from django_glue.access.actions import BaseGlueActionType


class ModelObjectGlueAction(BaseGlueActionType):
    GET = 'get'
    UPDATE = 'update'
    DELETE = 'delete'
    METHOD = 'method'

    def required_access(self) -> Access:
        if self.value in ['get', 'method']:
            return Access.VIEW
        elif self.value in ['update']:
            return Access.CHANGE
        elif self.value == 'delete':
            return Access.DELETE
        else:
            raise ValueError('That is not a valid action on a glue model object.')

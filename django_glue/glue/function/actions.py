from django_glue.access.access import Access
from django_glue.access.actions import BaseGlueActionType


class FunctionGlueAction(BaseGlueActionType):
    CALL = 'call'

    def required_access(self) -> Access:
        if self.value == 'call':
            return Access.VIEW
        else:
            raise ValueError('That is not a valid action on a glue function.')

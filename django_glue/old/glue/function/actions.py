from django_glue.access.access import Access
from django_glue.access.actions import BaseAction


class FunctionGlueAction(BaseAction):
    CALL = 'call'

    def required_access(self) -> Access:
        if self.value == 'call':
            return Access.VIEW
        else:
            raise ValueError('That is not a valid action on a glue function.')

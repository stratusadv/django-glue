from django_glue.access.access import GlueAccess
from django_glue.access.actions import GlueAction


class GlueFunctionAction(GlueAction):
    CALL = 'call'

    def required_access(self) -> GlueAccess:
        if self.value == 'call':
            return GlueAccess.VIEW
        else:
            raise ValueError('That is not a valid action on a glue query set.')

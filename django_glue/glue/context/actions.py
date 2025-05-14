from django_glue.access.access import Access
from django_glue.access.actions import BaseAction


class ContextGlueAction(BaseAction):
    GET = 'get'

    def required_access(self) -> Access:
        if self.value == 'get':
            return Access.VIEW

        message = 'Invalid action on a glue context.'
        raise ValueError(message)

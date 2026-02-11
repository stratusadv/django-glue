from django_glue.access.access import Access
from django_glue.access.actions import BaseAction


class TemplateGlueAction(BaseAction):
    GET = 'get'

    def required_access(self) -> Access:
        if self.value == 'get':
            return Access.VIEW
        else:
            raise ValueError('That is not a valid action on a glue query set.')

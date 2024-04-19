from django_glue.access.access import GlueAccess
from django_glue.access.actions import GlueAction


class GlueQuerySetAction(GlueAction):
    ALL = 'all'
    FILTER = 'filter'
    GET = 'get'
    UPDATE = 'update'
    DELETE = 'delete'
    METHOD = 'method'

    def required_access(self) -> GlueAccess:
        if self.value in ['get', 'all', 'filter']:
            return GlueAccess.VIEW
        elif self.value in ['update', 'method']:
            return GlueAccess.CHANGE
        elif self.value == 'delete':
            return GlueAccess.DELETE
        else:
            raise ValueError('That is not a valid action on a glue query set.')

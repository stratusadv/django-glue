from django_glue.access.access import GlueAccess
from django_glue.access.actions import GlueAction


class GlueModelObjectAction(GlueAction):
    GET = 'get'
    UPDATE = 'update'
    DELETE = 'delete'
    METHOD = 'method'

    def required_access(self) -> GlueAccess:
        if self.value in ['get', 'method']:
            return GlueAccess.VIEW
        elif self.value in ['update']:
            return GlueAccess.CHANGE
        elif self.value == 'delete':
            return GlueAccess.DELETE
        else:
            raise ValueError('That is not a valid action on a glue model object.')

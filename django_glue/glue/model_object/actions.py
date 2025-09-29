from typing import Type

from django_glue.access.access import Access
from django_glue.access.actions import BaseAction
from django_glue.glue.post_data import MethodActionKwargs, BaseActionKwargs, \
    UpdateActionKwargs


class ModelObjectGlueAction(BaseAction):
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

    @property
    def action_kwargs_type(self) -> Type[BaseActionKwargs] | None:
        match self.value:
            case 'get':
                return BaseActionKwargs
            case 'update':
                return UpdateActionKwargs
            case 'delete':
                return BaseActionKwargs
            case 'method':
                return MethodActionKwargs
            case _:
                raise ValueError('That is not a valid action on a glue model object.')

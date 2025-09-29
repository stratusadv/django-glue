from enum import Enum
from typing import Sequence

from django.db.models import Model
from pydantic import BaseModel, ValidationError

from django_glue.access.access import Access
from django_glue.constants import NONE_DUNDER_KEY, ALL_DUNDER_KEY
from django_glue.glue.enums import GlueType
from django_glue.glue.glue import BaseModelGlue, GlueActionResult, \
    ModelGlueInstanceFieldConfig
from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.post_data import BaseActionKwargs, UpdateActionKwargs, \
    MethodActionKwargs
from django_glue.session import Session
from django_glue.settings import DJANGO_GLUE_SESSION_NAME


class ModelObjectGlue(BaseModelGlue):
    """
    A glue wrapper for a single instance of a django model. Exposes a list of actions that can be performed on the
    underlying model object via the glue API.
    """
    def __init__(
            self,
            unique_name: str,
            session: Session,
            model_instance: Model,
            access: Access | str = Access.VIEW,
            field_config: ModelGlueInstanceFieldConfig | None = None,
            data: dict | None = None,
    ):
        super().__init__(
            unique_name=unique_name,
            session=session,
            access=access,
            field_config=field_config,
            model_class=model_instance.__class__,
            data=data
        )

        self.model_instance = model_instance

    def _glue_type(self) -> GlueType:
        return GlueType.MODEL_OBJECT

    def get(self) -> GlueActionResult:
        self.session[DJANGO_GLUE_SESSION_NAME][self.unique_name].data = {
            field_name: getattr(self.model_instance, field_name)
            for field_name in self._included_field_names
        }
        self.session.set_modified()

        return GlueActionResult(
            success=True,
            message='Successfully retrieved model glue data'
        )

    def update(self, kwargs: UpdateActionKwargs):
        for key, value in kwargs.fields.items():
            if key in self._included_field_names:
                if hasattr(self.model_instance, key):
                    setattr(self.model_instance, key, value)
            else:
                raise

        self.model_instance.save()

        self.get()

        return GlueActionResult(
            success=True,
            message='Successfully updated model glue data'
        )

    def method(self, kwargs: MethodActionKwargs):
        if kwargs.method in self.field_config.method_names and hasattr(self.model_class, kwargs.method):
            _method = getattr(self.model_instance, kwargs.method)

            if self._check_valid_method_kwargs(_method, kwargs.method_kwargs):
                type_set_kwargs = self._type_set_method_kwargs(_method, kwargs.method_kwargs)

                return _method(**type_set_kwargs)

        return GlueActionResult(
            success=False,
            message=f'Method "{kwargs.method}" not available for model object'
        )

    def process_action(
        self,
        action: ModelObjectGlueAction,
        action_kwargs: BaseActionKwargs | None = None,
    ) -> GlueActionResult:
        message = f'Successfully performed action {action.value} on model object'

        if action_kwargs:
            try:
                action_kwargs = action.action_kwargs_type.model_validate(
                    action_kwargs.model_dump()
                )
            except ValidationError as e:
                return GlueActionResult(
                    success=False,
                    message=f'Invalid action kwargs for action "{action.value}"'
                )

        match action:
            case ModelObjectGlueAction.GET:
                self.get()
            case ModelObjectGlueAction.UPDATE:
                self.update(action_kwargs)
            case ModelObjectGlueAction.DELETE:
                self.model_instance.delete()
            case ModelObjectGlueAction.METHOD:
                self.method(action_kwargs)

        return GlueActionResult(success=True, message=message)
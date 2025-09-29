from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Optional, Type

from django.db.models import Model

from django_glue.access.access import Access
from django_glue.form.field.factories import FormFieldFactory
from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.model_object.fields.glue import ModelFieldMetaGlue, ModelFieldGlue
from django_glue.glue.model_object.glue import ModelGlueFieldConfig, \
    ModelGlueFieldFilterMode
from django_glue.glue.post_data import BaseActionKwargs
from django_glue.session import Session
from django_glue.session.data import BaseModelGlueSessionData
from django_glue.settings import DJANGO_GLUE_MODEL_CONFIGS_SESSION_NAME


class BaseGlue(ABC):
    def __init__(
        self,
        unique_name: str,
        session: Session,
        access: Access | str = Access.VIEW
    ):
        if isinstance(access, str):
            access = Access(access)

        self.session = session
        self.access = access
        self.unique_name = unique_name

    def __post_init__(self):
        # This needs to be in post-init to account for any changes made in subclass
        # __init__ methods after the super call
        self._register_to_session()

    @abstractmethod
    def _register_to_session(self):
        raise NotImplemented('All concrete subclasses of BaseGlue must implement _register_to_session')

    @abstractmethod
    def process_action(self,
        action: ModelObjectGlueAction,
        action_kwargs: BaseActionKwargs
    ) -> GlueActionResult:
        raise NotImplemented('All concrete subclasses of BaseGlue must implement process_action')


@dataclass
class GlueActionResult:
    success: bool
    message: str
    data: Optional[dict] = None


class BaseModelGlue(BaseGlue, ABC):
    session_data: BaseModelGlueSessionData

    def __init__(
            self,
            unique_name: str,
            session: Session,
            field_config: ModelGlueFieldConfig,
            model_class: Type[Model],
            access: Access | str = Access.VIEW
    ):
        self.model_class = model_class
        self.field_config = field_config

        super().__init__(unique_name, session, access)

    @cached_property
    def _included_field_names(self):
        if self.field_config.mode == ModelGlueFieldFilterMode.INCLUDE:
            return self.field_config.fields
        else:
            return [
                field.name
                for field in self.model_class._meta.get_fields()
                if field.name not in self.field_config.fields
            ]

    def _register_to_session(self):
        if self.session_data.model_name not in self.session[DJANGO_GLUE_MODEL_CONFIGS_SESSION_NAME].keys():
            self.session[DJANGO_GLUE_MODEL_CONFIGS_SESSION_NAME][self.session_data.model_name] = {}

        model_glue_field_config = self.session[DJANGO_GLUE_MODEL_CONFIGS_SESSION_NAME][self.model_class._meta.model_name]

        for field_name in self._included_field_names:
            if field_name not in model_glue_field_config.keys():
                model_field = self.model_class._meta.get_field(field_name)

                _meta = ModelFieldMetaGlue(
                    type=model_field.get_internal_type(),
                    name=model_field.name,
                    glue_field=FormFieldFactory(model_field).factory_method()
                )

                model_field_glue = ModelFieldGlue(
                    name=model_field.name,
                    value=None,
                    _meta=_meta
                )

                model_glue_field_config[field_name].append(model_field_glue)

        self.session.set_modified()

    @staticmethod
    def _check_valid_method_kwargs(method: Callable, kwargs: Optional[dict]) -> bool:
        for kwarg in kwargs:
            if kwarg not in inspect.signature(method).parameters.keys():
                return False
        return True

    @staticmethod
    def _type_set_method_kwargs(method: Callable, kwargs: Optional[dict]) -> dict:
        type_set_kwargs = {}

        # This is a dict consisting of all kwargs and there type annotations (If they have type annotations)
        annotations = inspect.getfullargspec(method).annotations

        for kwarg in kwargs:
            if kwarg in annotations:
                # Converts the kwarg to match the type specified in on the methods kwargs
                type_set_kwargs[kwarg] = inspect.getfullargspec(method).annotations[
                    kwarg](kwargs[kwarg])
            else:
                # If there is not a type annotation, the value remains the same
                type_set_kwargs[kwarg] = kwargs[kwarg]

        return type_set_kwargs
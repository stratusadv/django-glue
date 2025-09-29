from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import Callable, Optional, Type, Sequence

from django.db.models import Model
from pydantic import BaseModel

from django_glue.access.access import Access
from django_glue.constants import NONE_DUNDER_KEY, ALL_DUNDER_KEY
from django_glue.form.field.factories import FormFieldFactory
from django_glue.glue.enums import GlueType
from django_glue.glue.model_object.actions import ModelObjectGlueAction
from django_glue.glue.model_object.fields.glue import ModelFieldMetaGlue, ModelFieldGlue
from django_glue.glue.post_data import BaseActionKwargs
from django_glue.session import Session
from django_glue.session.data import BaseModelGlueSessionData, BaseGlueSessionData
from django_glue.settings import DJANGO_GLUE_MODEL_FIELD_DATA_SESSION_NAME, \
    DJANGO_GLUE_SESSION_NAME, DJANGO_GLUE_MODEL_GLUE_INSTANCE_FIELD_CONFIG_NAME, \
    DJANGO_GLUE_MODEL_GLUE_INSTANCE_DATA_NAME


class BaseGlue(ABC):
    def __init__(
        self,
        unique_name: str,
        session: Session,
        access: Access | str = Access.VIEW,
        **kwargs,
    ):
        if isinstance(access, str):
            access = Access(access)

        self.session = session
        self.access = access
        self.unique_name = unique_name
        self._register_to_session(**kwargs)
        self.session.set_modified()

        if not hasattr(self, 'session_data'):
            raise Exception('session_data must be set in the _register_to_session method of a concrete subclass of BaseGlue')
        if not isinstance(self.session_data, BaseGlueSessionData):
            raise Exception('session_data must be an instance of BaseGlueSessionData')

    @abstractmethod
    def _register_to_session(self, **session_register_kwargs):
        raise NotImplemented('All concrete subclasses of BaseGlue must implement _register_to_session')

    @abstractmethod
    def process_action(self,
        action: ModelObjectGlueAction,
        action_kwargs: BaseActionKwargs
    ) -> GlueActionResult:
        raise NotImplemented('All concrete subclasses of BaseGlue must implement process_action')

    @abstractmethod
    @property
    def _glue_type(self) -> GlueType:
        """
        Returns the GlueType of the glue object.
        """
        raise NotImplemented('All concrete subclasses of BaseGlue must implement glue_type')


@dataclass
class GlueActionResult:
    success: bool
    message: str
    data: Optional[dict] = None


class ModelGlueFieldFilterMode(str, Enum):
    INCLUDE = 'include'
    EXCLUDE = 'exclude'


class ModelGlueInstanceFieldConfig(BaseModel):
    """
    Represents field configuration for a single given instance of a BaseModelGlue
    """
    field_names: Sequence[str] = (ALL_DUNDER_KEY,),
    method_names: Sequence[str] = (NONE_DUNDER_KEY,),
    field_filter_mode: ModelGlueFieldFilterMode = ModelGlueFieldFilterMode.INCLUDE


class BaseModelGlue(BaseGlue, ABC):
    def _register_to_session(
        self,
        model_class: Type[Model],
        access: Access | str = Access.VIEW,
        field_config: ModelGlueInstanceFieldConfig | None = None,
        data: dict | None = None,
    ):
        self.model_class = model_class
        self.field_config = field_config or self._get_session_instance_field_config_or_default()
        self.data = data or self._get_session_instance_object_data_or_default()
        self.session_data = BaseModelGlueSessionData(
            unique_name=self.unique_name,
            model_name=self.model_class._meta.model_name,
            access=self.access,
            app_label=self.model_class._meta.app_label,
            glue_type=self._glue_type,
            field_config=self.field_config,
            data=self.data,
        )
        self.session[DJANGO_GLUE_SESSION_NAME][DJANGO_GLUE_SESSION_NAME][self.unique_name] = self.session_data
        self._register_model_field_meta_to_session()

    def _get_session_instance_object_data_or_default(self):
        try:
            return self.session[DJANGO_GLUE_SESSION_NAME][DJANGO_GLUE_SESSION_NAME][
            self.unique_name][DJANGO_GLUE_MODEL_GLUE_INSTANCE_DATA_NAME]
        except KeyError:
            return {}

    def _get_session_instance_field_config_or_default(self) -> ModelGlueInstanceFieldConfig:
        try:
            return ModelGlueInstanceFieldConfig(**self.session[DJANGO_GLUE_SESSION_NAME][DJANGO_GLUE_SESSION_NAME][
            self.unique_name][DJANGO_GLUE_MODEL_GLUE_INSTANCE_FIELD_CONFIG_NAME])
        except KeyError:
            return ModelGlueInstanceFieldConfig()

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

    def _register_model_field_meta_to_session(self):
        model_name = self.model_class._meta.model_name

        if model_name not in self.session[DJANGO_GLUE_MODEL_FIELD_DATA_SESSION_NAME].keys():
            self.session[DJANGO_GLUE_MODEL_FIELD_DATA_SESSION_NAME][model_name] = {}

        model_field_data = self.session[DJANGO_GLUE_MODEL_FIELD_DATA_SESSION_NAME][self.model_class._meta.model_name]

        for field_name in self._included_field_names:
            if field_name not in model_field_data.keys():
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

                model_field_data[field_name].append(model_field_glue)

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
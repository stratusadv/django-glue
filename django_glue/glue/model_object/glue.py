from __future__ import annotations

from typing import Union, Any, Callable

from django.db.models import Model

from django_glue.access.access import Access
from django_glue.constants import ALL_DUNDER_KEY, NONE_DUNDER_KEY
from django_glue.glue.enums import GlueType
from django_glue.glue.glue import BaseGlue
from django_glue.glue.model_object.fields.glue import ModelFieldsGlue
from django_glue.glue.model_object.session_data import ModelObjectGlueSessionData
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class ModelObjectGlue(BaseGlue):
    def __init__(
            self,
            unique_name: str,
            model_object: Model,
            access: Union[Access, str] = Access.VIEW,
            included_fields: tuple = (ALL_DUNDER_KEY,),
            excluded_fields: tuple = (NONE_DUNDER_KEY,),
            included_methods: tuple = (NONE_DUNDER_KEY,),
    ):
        super().__init__(unique_name, GlueType.MODEL_OBJECT, access)

        self.model_object = model_object
        self.model = model_object._meta.model

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        self.fields: ModelFieldsGlue = self.generate_field_data()

    def call_method(self, method_name: str, method_kwargs: dict) -> Callable | None:
        if method_name in self.included_methods and hasattr(self.model, method_name):
            method = getattr(self.model_object, method_name)

            if check_valid_method_kwargs(method, method_kwargs):
                type_set_kwargs = type_set_method_kwargs(method, method_kwargs)

                return method(**type_set_kwargs)

        return None

    def generate_field_data(self, include_values: bool = True) -> ModelFieldsGlue:
        model_fields = ModelFieldsGlue.from_model_object(
            model=self.model,
            included_fields=self.included_fields,
            excluded_fields=self.excluded_fields
        )

        if include_values:
            model_fields.load_values_from_model_object(self.model_object)

        return model_fields

    def generate_method_data(self) -> list[str]:
        methods_list = list()

        for method in self.included_methods:
            if hasattr(self.model_object, method):
                methods_list.append(method)
            elif method == NONE_DUNDER_KEY:
                pass
            else:
                raise KeyError(f'Method "{method}" is invalid for model type "{self.model.__class__.__name__}"')

        return methods_list

    def to_session_data(self) -> ModelObjectGlueSessionData:
        return ModelObjectGlueSessionData(
            glue_type=self.glue_type,
            access=self.access,
            unique_name=self.unique_name,
            fields=self.generate_field_data(include_values=False).to_dict(), # Why is to_dict called here? Shouldn't this be .fields?
            app_label=self.model_object._meta.app_label,
            model_name=self.model_object._meta.model_name,
            object_pk=self.model_object.pk,
            included_fields=self.included_fields,
            exclude_fields=self.excluded_fields,
            methods=self.generate_method_data(),
        )

    def update(self, updated_fields: dict[str, Any]):
        for key, value in updated_fields.items():
            if hasattr(self.model_object, key):
                setattr(self.model_object, key, value)

        self.model_object.save()

        self.fields = self.generate_field_data()

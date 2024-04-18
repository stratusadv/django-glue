from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Any, Type, Optional, Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.access.enums import GlueAccess
from django_glue.form.utils import glue_form_field_from_model_field
from django_glue.form.fields import GlueFormField
from django_glue.handler.enums import GlueConnection

from django_glue.response.data import GlueJsonData
from django_glue.session.data import GlueContextData, GlueMetaData
from django_glue.utils import field_name_included


@dataclass
class GlueModelField:
    name: str
    value: Any
    form_field: GlueFormField

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'value': self.value,
            'form_field': self.form_field.to_dict()
        }


@dataclass
class GlueEntity(ABC):

    @abstractmethod
    def to_context_data(self) -> GlueContextData:
        pass

    @abstractmethod
    def to_meta_data(self) -> GlueMetaData:
        pass

    def to_json_data(self) -> GlueJsonData:
        pass


@dataclass
class GlueModelObject(GlueEntity):
    unique_name: str
    model_object: Model
    fields: list[GlueModelField] = field(default_factory=list)

    access: Union[GlueAccess, str] = GlueAccess.VIEW
    connection: GlueConnection = GlueConnection.MODEL_OBJECT

    included_fields: tuple = ('__all__',),
    excluded_fields: tuple = ('__none__',),
    included_methods: tuple = ('__none__',),

    content_type: ContentType = ...
    app_label: str = ...
    model: Type[Model] = ...
    object_pk: Optional[int] = ...

    def __post_init__(self):
        self.fields = self.generate_field_data()
        self.content_type = ContentType.objects.get_for_model(self.model_object)
        self.app_label = self.content_type.app_label
        self.model = self.content_type.model
        self.object_pk = self.model_object.pk

        if isinstance(self.access, str):
            self.access = GlueAccess(self.access)

    def fields_to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}

    def generate_field_data(self) -> list[GlueModelField]:
        field_data = []
        for django_field in self.model._meta.fields:
            if field_name_included(django_field.name, self.included_fields, self.excluded_fields):
                field_data.append(GlueModelField(
                    name=django_field.name,
                    value=getattr(self.model_object, django_field.name),
                    form_field=glue_form_field_from_model_field(django_field, self.model_object)
                ))
        return field_data

    def generate_method_data(self):
        methods_list = list()

        if self.included_methods[0] != '__none__':
            for method in self.included_methods:
                if hasattr(self.model_object, method):
                    methods_list.append(method)
                else:
                    raise f'Method "{method}" is invalid for model type "{self.model.__class__.__name__}"'

        return methods_list

    def to_context_data(self) -> GlueContextData:
        return GlueContextData(
            connection=self.connection,
            access=self.access,
            fields=self.fields,
            methods=self.generate_method_data(),
        )

    def to_meta_data(self) -> GlueMetaData:
        # Todo: not sure of model is the model or model name here
        return GlueMetaData(
            app_label=self.app_label,
            model=self.model._meta.model_name,
            object_pk=self.model_object.pk,
            exclude=self.excluded_fields,
            methods=self.included_methods,
            fields=self.fields
        )

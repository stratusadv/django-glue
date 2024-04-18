from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Type, Optional, Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.access.enums import GlueAccess
from django_glue.data_classes import GlueContextData, GlueMetaData
from django_glue.form.factories import form_field_from_django_model_field
from django_glue.form.fields import FormField
from django_glue.request.enums import GlueConnection
from django_glue.utils import field_name_included


@dataclass
class GlueEntity(ABC):

    @abstractmethod
    def to_context_data(self) -> GlueContextData:
        pass

    @abstractmethod
    def to_meta_data(self) -> GlueMetaData:
        pass


# This should know all the information about itself.
@dataclass
class GlueModelObject(GlueEntity):
    model_object: Model

    access: Union[GlueAccess, str] = GlueAccess.VIEW
    fields: tuple = ('__all__',),
    exclude: tuple = ('__none__',),
    methods: tuple = ('__none__',),

    content_type: ContentType = ...
    app_label: str = ...
    model: Type[Model] = ...
    object_pk: Optional[int] = ...

    def __post_init__(self):
        self.content_type = ContentType.objects.get_for_model(self.model_object)
        self.app_label = self.content_type.app_label
        self.model = self.content_type.model
        self.object_pk = self.model_object.pk

        if isinstance(self.access, str):
            self.access = GlueAccess(self.access)

    def generate_field_data(self) -> list['GlueModelField']:
        field_data = []
        for field in self.model._meta.fields:
            if field_name_included(field.name, self.fields, self.exclude):
                field_data.append(GlueModelField(
                    name=field.name,
                    value=getattr(self.model_object, field.name),
                    form_field=form_field_from_django_model_field(field, self.model_object)
                ))
        return field_data

    def generate_method_data(self):
        pass

    def to_context_data(self) -> GlueContextData:
        return GlueContextData(
            connection=GlueConnection.MODEL_OBJECT,
            access=self.access,
            fields=self.generate_field_data(),
            methods=self.generate_method_data(),
        )

    def to_meta_data(self) -> GlueMetaData:
        # Todo: not sure of model is the model or model name here
        return GlueMetaData(
            app_label=self.app_label,
            model=self.model._meta.model_name,
            object_pk=self.model_object.pk,
            exclude=self.exclude,
            methods=self.methods,
            fields=self.fields
        )


@dataclass
class GlueModelField:
    name: str
    value: Any
    form_field: FormField

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_django_field(cls, field):
        pass

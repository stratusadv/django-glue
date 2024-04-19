from dataclasses import dataclass, field
from typing import Type, Optional, Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.access.enums import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.data import GlueModelField
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.enums import GlueConnection
from django_glue.utils import generate_field_dict


@dataclass
class GlueModelObject(GlueEntity):
    unique_name: str
    model_object: Model
    # fields: list[GlueModelField] = field(default_factory=list)
    fields: dict = field(default_factory=dict)

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
        self.content_type = ContentType.objects.get_for_model(self.model_object)
        self.app_label = self.content_type.app_label
        self.model = self.content_type.model_class()
        self.object_pk = self.model_object.pk
        self.fields = self.generate_field_data()

        if isinstance(self.access, str):
            self.access = GlueAccess(self.access)

    def fields_to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}

    # def generate_response_data(self) -> list['GlueModelObjectJsonData']:
    def generate_field_data(self) -> dict:
        return generate_field_dict(self.model_object, self.included_fields, self.excluded_fields)
        # field_data = []
        # Todo: Generate field data
        # for django_field in self.model._meta.fields:
        #     if field_name_included(django_field.name, self.included_fields, self.excluded_fields):
        #         field_data.append(GlueModelField(
        #             name=django_field.name,
        #             value=getattr(self.model_object, django_field.name),
        #             form_field=glue_form_field_from_model_field(django_field, self.model_object)
        #         ))

        # return

    def generate_method_data(self):
        methods_list = list()

        if self.included_methods[0] != '__none__':
            for method in self.included_methods:
                if hasattr(self.model_object, method):
                    methods_list.append(method)
                else:
                    raise f'Method "{method}" is invalid for model type "{self.model.__class__.__name__}"'

        return methods_list

    def to_session_data(self) -> GlueModelObjectSessionData:
        return GlueModelObjectSessionData(
            connection=self.connection,
            access=self.access,
            app_label=self.app_label,
            model_name=self.model._meta.model_name,
            object_pk=self.model_object.pk,
            included_fields=self.included_fields,
            exclude_fields=self.excluded_fields,
            methods=self.generate_method_data(),
        )

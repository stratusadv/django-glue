from typing import Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.access.enums import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.enums import GlueConnection
from django_glue.utils import generate_field_dict


class GlueModelObject(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            model_object: Model,
            access: Union[GlueAccess, str] = GlueAccess.VIEW,
            connection: GlueConnection = GlueConnection.MODEL_OBJECT,
            included_fields: tuple = ('__all__',),
            excluded_fields: tuple = ('__none__',),
            included_methods: tuple = ('__none__',),
    ):
        super().__init__(unique_name, connection, access)

        self.model_object = model_object

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        self.fields = self.generate_field_data()

        self.content_type = ContentType.objects.get_for_model(self.model_object)
        self.app_label = self.content_type.app_label
        self.model = self.content_type.model_class()
        self.object_pk = self.model_object.pk
        self.fields = self.generate_field_data()

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
            unique_name=self.unique_name,
            app_label=self.app_label,
            model_name=self.model._meta.model_name,
            object_pk=self.model_object.pk,
            included_fields=self.included_fields,
            exclude_fields=self.excluded_fields,
            methods=self.generate_method_data(),
        )

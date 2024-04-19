from typing import Union

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

from django_glue.access.enums import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.responses import GlueModelField, GlueModelObjectJsonData
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.enums import GlueConnection
from django_glue.utils import generate_field_dict, field_name_included, generate_field_attr_dict


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
            content_type: ContentType = None,
    ):
        super().__init__(unique_name, connection, access)

        self.model_object = model_object

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        if content_type is None:
            self.content_type = ContentType.objects.get_for_model(self.model_object)
        else:
            self.content_type = content_type

        self.app_label = self.content_type.app_label
        self.model = self.content_type.model_class()
        self.object_pk = self.model_object.pk
        self.fields = self.generate_field_data()

    def generate_field_data(self) -> list[GlueModelField]:
        # Todo: This needs to be cleaned up.
        fields = []

        for field in self.model._meta.fields:
            try:
                if field_name_included(field.name, self.included_fields, self.excluded_fields):
                    if hasattr(field, 'get_internal_type'):
                        if field.name == 'id':
                            # field_value = json_model['pk']
                            field_value = self.model_object.pk
                            field_attr = ''
                        else:
                            field_value = getattr(self.model_object, field.name)
                            # field_value = json_model['fields'][field.name]
                            field_attr = generate_field_attr_dict(field)

                        # Todo: Field name logic is duplicated
                        if field.many_to_one or field.one_to_one:
                            field_name = field.name + '_id'
                        else:
                            field_name = field.name

                        fields.append(GlueModelField(
                            name=field.name,
                            type=field.get_internal_type(),
                            value=field_value,
                            html_attr=field_attr
                        ))
                        # fields_dict[field_name] = {
                        #     'type': field.get_internal_type(),
                        #     'value': field_value,
                        #     'html_attr': field_attr
                        # }

                        #     GlueModelFieldData(
                        #     type=field.get_internal_type(),
                        #     value=field_value,
                        #     html_attr=field_attr,
                        # ).to_dict()

            except:
                raise f'Field "{field.name}" is invalid field or exclude for model type "{self.model.__class__.__name__}"'

        return fields

    def fields_to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}

    def to_object_json_data(self) -> GlueModelObjectJsonData:
        return GlueModelObjectJsonData(fields=self.fields)

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

    def update(self):
        self.fields = self.generate_field_data()
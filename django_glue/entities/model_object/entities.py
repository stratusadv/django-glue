from typing import Union, Any

from django.db.models import Model

from django_glue.access.access import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.responses import GlueModelField, GlueModelObjectJsonData
from django_glue.entities.model_object.sessions import GlueModelObjectSessionData
from django_glue.handler.enums import GlueConnection
from django_glue.utils import field_name_included, generate_field_attr_dict, \
    check_valid_method_kwargs, type_set_method_kwargs


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
        self.model = model_object._meta.model

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        self.fields: list[GlueModelField] = self.generate_field_data()

    def call_method(self, method_name, method_kwargs):
        if method_name in self.included_methods and hasattr(self.model, method_name):
            method = getattr(self.model_object, method_name)

            if check_valid_method_kwargs(method, method_kwargs):
                type_set_kwargs = type_set_method_kwargs(method, method_kwargs)

                return method(**type_set_kwargs)

        return None

    def fields_to_dict(self):
        return {field.name: field.to_dict() for field in self.fields}

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

    def generate_method_data(self):
        methods_list = list()

        if self.included_methods[0] != '__none__':
            for method in self.included_methods:
                if hasattr(self.model_object, method):
                    methods_list.append(method)
                else:
                    raise f'Method "{method}" is invalid for model type "{self.model.__class__.__name__}"'

        return methods_list

    def to_response_data(self) -> GlueModelObjectJsonData:
        return GlueModelObjectJsonData(fields=self.fields)

    def to_session_data(self) -> GlueModelObjectSessionData:
        return GlueModelObjectSessionData(
            connection=self.connection,
            access=self.access,
            unique_name=self.unique_name,
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

from typing import Union, Any

from django.db.models import Model

from django_glue.access.access import GlueAccess
from django_glue.entities.base_entity import GlueEntity
from django_glue.entities.model_object.fields.entities import (
    GlueModelField,
    GlueModelFieldMeta,
    GlueModelFields
)
from django_glue.entities.model_object.fields.factories import model_object_fields_from_model
from django_glue.entities.model_object.fields.utils import (
    field_name_included,
    get_field_value_from_model_object
)
from django_glue.entities.model_object.session_data import GlueModelObjectSessionData
from django_glue.form.field.entities import GlueAnnotationField
from django_glue.handler.enums import GlueConnection
from django_glue.utils import check_valid_method_kwargs, type_set_method_kwargs


class GlueModelObject(GlueEntity):
    def __init__(
            self,
            unique_name: str,
            model_object: Model,
            access: Union[GlueAccess, str] = GlueAccess.VIEW,
            included_fields: tuple = ('__all__',),
            excluded_fields: tuple = ('__none__',),
            included_methods: tuple = ('__none__',),
    ):
        super().__init__(unique_name, GlueConnection.MODEL_OBJECT, access)

        self.model_object = model_object
        self.model = model_object._meta.model

        self.included_fields = included_fields
        self.excluded_fields = excluded_fields
        self.included_methods = included_methods

        self.fields: GlueModelFields = self.generate_field_data()

    def call_method(self, method_name, method_kwargs):
        if method_name in self.included_methods and hasattr(self.model, method_name):
            method = getattr(self.model_object, method_name)

            if check_valid_method_kwargs(method, method_kwargs):
                type_set_kwargs = type_set_method_kwargs(method, method_kwargs)

                return method(**type_set_kwargs)

        return None

    def generate_field_data(self, include_values: bool = True) -> GlueModelFields:
        glue_model_fields = model_object_fields_from_model(
            model=self.model,
            included_fields=self.included_fields,
            excluded_fields=self.excluded_fields
        )

        field_names = {
            field.name
            for field in glue_model_fields.fields
        }

        instance_dict_keys = set(self.model_object.__dict__.keys())
        possible_annotated_fields = instance_dict_keys - field_names - {'_state'}

        for attr_name in possible_annotated_fields:
            if attr_name.startswith('_'):
                continue

            value = getattr(self.model_object, attr_name)

            if callable(value):
                continue

            if field_name_included(attr_name, self.included_fields, self.excluded_fields):
                if not attr_name.endswith('_id'):
                    _meta = GlueModelFieldMeta(
                        type='GlueAnnotationField',
                        name=attr_name,
                        glue_field=GlueAnnotationField(attr_name)
                    )

                    field_value = value if include_values else None

                    glue_model_fields.fields.append(
                        GlueModelField(
                            name=attr_name,
                            value=field_value,
                            _meta=_meta
                        )
                    )

        if include_values:
            for field in glue_model_fields.fields:
                if field.name in field_names and field.value is None:
                    field.value = get_field_value_from_model_object(self.model_object, field)

        return glue_model_fields

    def generate_method_data(self):
        methods_list = []

        for method in self.included_methods:
            if hasattr(self.model_object, method):
                methods_list.append(method)
            elif method == '__none__':
                pass
            else:
                raise KeyError(f'Method "{method}" is invalid for model type "{self.model.__class__.__name__}"')

        return methods_list

    def to_session_data(self) -> GlueModelObjectSessionData:
        session_data_fields = self.generate_field_data(include_values=False).to_dict()

        annotated_value_map = {}

        for field in self.fields.fields:
            if field._meta.type == 'GlueAnnotationField':
                annotated_value_map[field.name] = field.value

        for field_name, field_data in session_data_fields.items():
            if field_data['_meta']['type'] == 'GlueAnnotationField':
                value = annotated_value_map.get(field_name)
                field_data['value'] = value

        return GlueModelObjectSessionData(
            connection=self.connection,
            access=self.access,
            unique_name=self.unique_name,
            fields=session_data_fields,
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

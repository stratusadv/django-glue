from __future__ import annotations

from functools import cached_property
from typing import Any, Literal, Mapping, Sequence, TYPE_CHECKING, cast

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict

from django_glue.access import GlueAccess
from django_glue.glue.attributes import Attribute, BaseGlueAttribute, GlueObjectAttribute, ReadableAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.model import ForeignKeyFieldAttribute, ModelFieldAttribute
from django_glue.glue.metadata import GlueMetadata
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.form.object import FormGlue
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy  # noqa: TC001
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db import models

ALL_FIELDS: Literal['__all__'] = '__all__'


class ModelGlue(ModelGlueFormConfigMixin, BaseGlue):

    namespace = 'model'
    globally_excluded_field_types = frozenset({'BinaryField'})

    def __init__(
        self,
        instance: models.Model,
        *,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        annotations: Sequence[str] = (),
        form: forms.ModelForm | None = None,
        forms: Mapping[str, forms.ModelForm] | None = None,
        select_related: Sequence[str] | None = None,
    ) -> None:
        super().__init__(name=name, access=access)
        self.instance = instance
        self.fields = (
            fields if fields == ALL_FIELDS else tuple(fields)
        )
        self.exclude = (
            exclude if exclude == ALL_FIELDS else tuple(exclude)
        )

        if not self.fields and not self.exclude:
            msg = 'ModelGlue requires at least one of fields or exclude.'
            raise ValueError(msg)

        # Only raise error for explicitly specified binary fields
        # When __all__ is used, binary fields are silently excluded in _included_fields
        if self.fields != ALL_FIELDS:
            binary_fields = [
                field_name
                for field_name in self.fields
                if self.instance._meta.get_field(field_name).get_internal_type()
                in self.globally_excluded_field_types
            ]
            if binary_fields:
                msg = (
                    'Binary fields cannot be included in ModelGlue attributes: '
                    f'{binary_fields}'
                )
                raise ValueError(
                    msg
                )

        self.annotations = annotations
        self.select_related = select_related or set()

        self.forms = self.normalize_forms(form, forms)
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}

    @property
    def attribute_providers(self) -> dict[str, Any]:
        return {'instance': self.instance}

    @property
    def identity(self) -> dict[str, Any]:
        instance = self.instance
        identity = {
            'model_class_path': f'{instance.__class__.__module__}.{instance.__class__.__name__}',
            'target_pk': instance.pk,
            'pk_field_name': instance._meta.pk.name, # type: ignore  # noqa: PGH003
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self.select_related:
            identity['select_related'] = list(self.select_related)

        return identity

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes = super().attributes

        for field_name in self._included_fields:
            field = self.instance._meta.get_field(field_name)

            # Use ForeignKeyFieldAttribute for FK/O2O fields
            if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                # Add the attname (e.g., parent_id) as a regular field for the raw FK value
                attributes[field.attname] = ModelFieldAttribute(
                    owner=self,
                    name=field.attname,
                    field=field,
                    instance=self.instance,
                    access=self._field_access(field_name),
                )
                # Add the FK field (e.g., parent) for the nested object
                attributes[field_name] = ForeignKeyFieldAttribute(
                    owner=self,
                    name=field_name,
                    field=field,
                    instance=self.instance,
                    access=self._field_access(field_name),
                    is_cached=self._is_fk_cached(field_name),
                )
            else:
                attributes[field_name] = ModelFieldAttribute(
                    owner=self,
                    name=field_name,
                    field=field,
                    instance=self.instance,
                    access=self._field_access(field_name),
                )

        attributes.update({
            annotation_name: ReadableAttribute(
                owner=self,
                name=annotation_name,
                access=GlueAccess.VIEW,
                target=self.instance,
            )
            for annotation_name in self._annotation_names
        })
        attributes.update(self._form_attributes())
        return attributes

    def _form_attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes: dict[str, BaseGlueAttribute] = {}
        default_attribute = None

        for form_name, form in self.forms.items():
            # Need to rebuild the form here in order to properly bind instance data!
            form = form.__class__(instance=self.instance)

            attribute_name = f'forms.{form_name}'
            form_attribute = GlueObjectAttribute(
                owner=self,
                name=attribute_name,
                access=self.access,
                glue_object=FormGlue(
                    form=form,
                    name=f'{self.name}.{attribute_name}',
                    access=self.access,
                ),
            )
            attributes[attribute_name] = form_attribute

            if form_name == 'default':
                default_attribute = form_attribute

        if default_attribute is not None:
            attributes['form'] = default_attribute

        return attributes

    @cached_property
    def _annotation_names(self) -> tuple[str, ...]:
        return tuple(self.annotations)

    @cached_property
    def _included_fields(self) -> list[str]:
        all_field_names = tuple(
            field.name
            for field in [*self.instance._meta.fields, *self.instance._meta.many_to_many]
        )
        names = all_field_names if self.fields == ALL_FIELDS or not self.fields else self.fields
        excluded = set(all_field_names) if self.exclude == ALL_FIELDS else set(self.exclude)
        return [
            name
            for name in names
            if name not in excluded
            and self.instance._meta.get_field(name).get_internal_type()
            not in self.globally_excluded_field_types
        ]

    @property
    def state(self) -> dict[str, Any]:
        self._validate()
        state = {}
        for name, attribute in self.attributes.items():
            if hasattr(attribute, 'state'):
                state[name] = attribute.state

        return state

    def _validate(self) -> None:
        """Run validation and populate _field_errors."""
        try:
            self.instance.full_clean()
            self._field_errors = {}
        except ValidationError as e:
            self._field_errors = e.message_dict if hasattr(e, 'message_dict') else {'__all__': e.messages}

    @cached_property
    def metadata(self) -> GlueMetadata:
        return GlueMetadata.from_payload({
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        })

    def _field_access(self, field_name: str) -> GlueAccess:
        field = self.instance._meta.get_field(field_name)
        return GlueAccess.CHANGE if field.editable else GlueAccess.VIEW

    def _is_fk_cached(self, field_name: str) -> bool:
        """Check if a FK field's related instance is already cached (via select_related)."""
        if field_name in self.select_related:
            return True
        field = self.instance._meta.get_field(field_name)
        return field.is_cached(self.instance)

    @classmethod
    def _from_policy(cls, policy: GluePolicy) -> ModelGlue:
        model_class = cast(
            'type[Model]',
            get_attr_from_path_string(policy.identity['model_class_path'])
        )

        target_pk = policy.identity.get('target_pk')
        select_related = policy.identity.get('select_related', [])

        if target_pk is None:
            instance = model_class()
        else:
            queryset = model_class.objects.all()
            if select_related:
                queryset = queryset.select_related(*select_related)
            instance = queryset.get(pk=target_pk)

        model_field_names = {
            field.name
            for field in [*model_class._meta.fields, *model_class._meta.many_to_many]
        }

        fields = []
        for attr in policy.attributes:
            if isinstance(attr, str):
                if attr in model_field_names:
                    fields.append(attr)
            else:
                # Nested policy - extract field name from policy name
                # e.g., "fights.1.red_corner" -> "red_corner"
                nested_name = attr.name
                if nested_name.startswith(policy.name + '.'):
                    field_name = nested_name[len(policy.name) + 1:]
                    if field_name in model_field_names:
                        fields.append(field_name)

        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {}),
            instance=instance
        )

        return cls(
            instance,
            name=policy.name,
            access=policy.access,
            fields=fields,
            forms=forms,
            select_related=select_related,
        )

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Apply client-provided state to the model instance."""
        self._loaded_state = state
        self._apply_state(state)

    def _apply_state(self, state: dict[str, Any]) -> None:
        """Apply state data directly to model fields."""
        for field_name in self._included_fields:
            field = self.instance._meta.get_field(field_name)
            if not field.editable:
                continue

            # Handle file fields from request.FILES
            if getattr(field, 'get_internal_type', lambda: '')() in {'FileField', 'ImageField'}:
                file_value = self._get_file_from_request(field_name)
                if file_value is not None:
                    setattr(self.instance, field_name, file_value)
                continue

            if field_name not in state:
                continue

            field_state = state[field_name]
            value = field_state.get('value') if isinstance(field_state, dict) else field_state

            if getattr(field, 'many_to_many', False):
                # M2M fields need special handling after save
                continue

            if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                value = self._pk_from_related_value(value)
                setattr(self.instance, field.attname, value)
                continue

            setattr(self.instance, field_name, value)

    def _get_file_from_request(self, field_name: str) -> Any:
        """Get a file from request.FILES for a field."""
        if not self.request or not self.request.FILES:
            return None

        return self.request.FILES.get(field_name)

    @Attribute(access=GlueAccess.VIEW, loads_state=False)
    def load(self) -> dict[str, Any]:
        return {'state': self.state}

    @Attribute(access=GlueAccess.CHANGE)
    def save(self) -> dict[str, Any]:
        try:
            self.instance.full_clean()
            self.instance.save()
            self._apply_m2m_state(self._loaded_state or {})
            return {  # noqa: TRY300
                'success': True,
                'errors': {}
            }
        except ValidationError as e:
            return {
                'success': False,
                'errors': e.message_dict if hasattr(e, 'message_dict') else {'__all__': e.messages}
            }

    def _apply_m2m_state(self, state: dict[str, Any]) -> None:
        """Apply M2M field values after the instance has been saved."""
        for field_name in self._included_fields:
            if field_name not in state:
                continue
            field = self.instance._meta.get_field(field_name)
            if not getattr(field, 'many_to_many', False):
                continue
            field_state = state[field_name]
            value = field_state.get('value') if isinstance(field_state, dict) else field_state
            pks = [self._pk_from_related_value(item) for item in value or []]
            getattr(self.instance, field_name).set(pks)

    @staticmethod
    def _pk_from_related_value(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get('pk', value.get('id'))
        return getattr(value, 'pk', value)

    @Attribute(access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        field_name: str | None = None,
        choice_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not field_name or field_name not in self._included_fields:
            return []

        field = self.instance._meta.get_field(field_name)
        related_model = getattr(field, 'related_model', None)
        if related_model is None:
            return []

        def serialize_choice(obj: Model) -> dict[str, Any]:
            choice = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice[choice_field] = getattr(obj, choice_field)
            return choice

        return [serialize_choice(obj) for obj in related_model.objects.all()]

    @Attribute(access=GlueAccess.DELETE)
    def delete(self) -> None:
        self.instance.delete()

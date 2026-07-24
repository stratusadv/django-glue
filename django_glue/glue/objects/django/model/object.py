from __future__ import annotations

from functools import cached_property
from typing import Any, Sequence, TYPE_CHECKING, cast

from django.core.exceptions import ValidationError

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute, ReadableAttribute, Attribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.model import ModelFieldAttribute
from django_glue.glue.metadata import GlueMetadata
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy  # noqa: TC001
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db.models import Model
    from django.db import models


class ModelGlue(BaseGlue):

    namespace = 'model'

    def __init__(
        self,
        instance: models.Model,
        *,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
        source_queryset: models.QuerySet | None = None,
    ) -> None:
        super().__init__(name=name, access=access)
        self.instance = instance
        self.fields = tuple(fields)
        self.exclude = tuple(exclude)
        self.source_queryset = source_queryset
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}

    @property
    def attribute_providers(self) -> dict[str, Any]:
        return {'instance': self.instance}

    @property
    def identity(self) -> dict[str, Any]:
        instance = self.instance
        return {
            'model_class_path': f'{instance.__class__.__module__}.{instance.__class__.__name__}',
            'target_pk': instance.pk,
            'pk_field_name': instance._meta.pk.name, # type: ignore  # noqa: PGH003
        }

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes = super().attributes | {
            field_name: ModelFieldAttribute(
                owner=self,
                name=field_name,
                field=self.instance._meta.get_field(field_name),
                instance=self.instance,
                access=self._field_access(field_name),
            )
            for field_name in self._included_fields
        }
        attributes.update({
            annotation_name: ReadableAttribute(
                owner=self,
                name=annotation_name,
                access=GlueAccess.VIEW,
                target=self.instance,
            )
            for annotation_name in self._annotation_names
        })
        return attributes

    @cached_property
    def _annotation_names(self) -> tuple[str, ...]:
        if self.source_queryset is None:
            return ()
        return tuple(self.source_queryset.query.annotations)

    @cached_property
    def _included_fields(self) -> list[str]:
        names = self.fields or tuple(
            field.name
            for field in [*self.instance._meta.fields, *self.instance._meta.many_to_many]
        )
        excluded = set(self.exclude)
        return [name for name in names if name not in excluded]

    @property
    def state(self) -> dict[str, Any]:
        self._validate()
        return {
            name: attribute.state
            for name, attribute in self.attributes.items()
            if hasattr(attribute, 'state')
        }

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

    @classmethod
    def _from_policy(cls, policy: GluePolicy) -> ModelGlue:
        model_class = cast(
            'type[Model]',
            get_attr_from_path_string(policy.identity['model_class_path'])
        )

        target_pk = policy.identity.get('target_pk')

        instance = model_class() if target_pk is None else model_class.objects.get(pk=target_pk)

        model_field_names = {
            field.name
            for field in [*model_class._meta.fields, *model_class._meta.many_to_many]
        }

        fields = [
            attribute_name
            for attribute_name in policy.attributes
            if attribute_name in model_field_names
        ]

        return cls(
            instance,
            name=policy.name,
            access=policy.access,
            fields=fields,
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
        return None

    @Attribute(access=GlueAccess.VIEW)
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

        def serialize_choice(obj) -> dict[str, Any]:
            choice = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice[choice_field] = getattr(obj, choice_field)
            return choice

        return [serialize_choice(obj) for obj in related_model.objects.all()]

    @Attribute(access=GlueAccess.DELETE)
    def delete(self) -> dict[str, Any]:
        self.instance.delete()
        return {}

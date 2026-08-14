from __future__ import annotations

from functools import cached_property
from typing import Any, Literal, Mapping, Sequence, TYPE_CHECKING, cast

from django.core.exceptions import ValidationError

from django_glue.access import GlueAccess
from django_glue.glue.attributes import (
    BaseGlueAttribute,
    DeclaredAttribute,
    GlueObjectAttribute,
    ReadOnlyAttribute,
)
from django_glue.glue.base import BaseGlue
from django_glue.glue.attributes.django.model import (
    ForeignKeyFieldAttribute,
    ModelFieldAttribute,
    RelatedSetFieldAttribute,
)
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.computed_attributes import (
    ComputedAttribute,
    GlueComputedAttributesMixin,
)
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.model_fields import ModelFieldResolutionMixin
# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy  # noqa: TC001
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django.db.models import Model

ALL_FIELDS: Literal['__all__'] = '__all__'


class ModelGlue(GlueComputedAttributesMixin, ModelGlueFormConfigMixin, ModelFieldResolutionMixin, BaseGlue):

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
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, Mapping[str, Sequence[str] | Literal['__all__']]] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
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
            non_includable_fields = [
                field_name
                for field_name in self.fields
                if not self._is_field_includable(field_name)
            ]
            if non_includable_fields:
                msg = (
                    f'Non-includable fields, including Binary fields, were found in the ModelGlue field initialization list: '
                    f'{non_includable_fields}'
                )
                raise ValueError(
                    msg
                )

        self.annotations = annotations
        self._select_related = set(select_related or ())
        self.related_field_config = self._normalize_related_field_config(related_field_config)
        self.initialize_computed_attributes(computed_attributes)

        self.forms = self.normalize_forms(form, forms)
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}

    def get_attribute_providers(self) -> dict[str, Any]:
        return {'instance': self.instance}

    def get_identity(self) -> dict[str, Any]:
        instance = self.instance
        identity = {
            'model_class_path': f'{instance.__class__.__module__}.{instance.__class__.__name__}',
            'target_pk': instance.pk,
            'pk_field_name': instance._meta.pk.name, # type: ignore  # noqa: PGH003
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self._select_related:
            identity['select_related'] = list(self._select_related)
        if self.related_field_config:
            identity['related_field_config'] = self.related_field_config
        identity |= self.computed_attributes_identity()

        return identity

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes = super().attributes

        for field_name in self._included_fields:
            # Handle reverse relations (no field object in _meta.get_field for these)
            if self._is_reverse_relation(field_name):
                attributes[field_name] = self._build_related_set_attribute(
                    field_name, 'reverse_fk',
                )
                continue

            field = self._get_model_field(field_name)

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
                if field_name == field.attname and field.name != field_name:
                    continue

                # Add the FK field (e.g., parent) for the nested object
                attributes[field_name] = ForeignKeyFieldAttribute(
                    owner=self,
                    name=field_name,
                    field=field,
                    instance=self.instance,
                    access=self._field_access(field_name),
                    is_cached=self._is_fk_cached(field_name),
                    related_fields=self.related_field_config.get(field_name, {}).get('fields'),
                    related_exclude=self.related_field_config.get(field_name, {}).get('exclude'),
                )

            # Use RelatedSetFieldAttribute for M2M fields
            elif getattr(field, 'many_to_many', False):
                attributes[field_name] = self._build_related_set_attribute(
                    field_name, 'm2m',
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
            annotation_name: ReadOnlyAttribute(
                owner=self,
                name=annotation_name,
                access=GlueAccess.VIEW,
                attr_owner_instance=self.instance,
            )
            for annotation_name in (*self._annotation_names, *self._computed_attribute_names)
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
                    loading_strategy=self.resolved_loading_strategy,
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

    @staticmethod
    def _normalize_related_field_config(
        related_field_config: Mapping[str, Mapping[str, Sequence[str] | Literal['__all__']]] | None,
    ) -> dict[str, dict[str, tuple[str, ...] | Literal['__all__']]]:
        normalized = {}
        for field_name, config in (related_field_config or {}).items():
            normalized[field_name] = {
                key: value if value == ALL_FIELDS else tuple(value)
                for key, value in config.items()
                if key in {'fields', 'exclude'} and value
            }
        return normalized

    @property
    def _model_meta(self) -> Any:
        """Return the Django model's _meta options."""
        return self.instance._meta

    def get_state(self) -> dict[str, Any]:
        self.hydrate_computed_attributes(self.instance)
        self._validate()
        state = {}
        for name, attribute in self.attributes.items():
            if hasattr(type(attribute), 'state'):
                state[name] = attribute.state

        return state

    def _validate(self) -> None:
        if (
            self._loaded_state is None
            or not self.access.has_access(GlueAccess.CHANGE)
        ):
            self._field_errors = {}
            return

        try:
            self.instance.full_clean()
            self._field_errors = {}
        except ValidationError as e:
            self._field_errors = (
                e.message_dict if hasattr(e, 'message_dict') else {'__all__': e.messages}
            )

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    def _field_access(self, field_name: str) -> GlueAccess:
        field = self._get_model_field(field_name)
        return GlueAccess.CHANGE if field.editable else GlueAccess.VIEW

    def _is_fk_cached(self, field_name: str) -> bool:
        """Check if a FK field's related instance is already cached (via select_related)."""
        if field_name in self._select_related:
            return True
        field = self._get_model_field(field_name)
        return field.is_cached(self.instance)

    def _is_prefetched(self, relation_name: str) -> bool:
        """Check if a relation was prefetched (via prefetch_related)."""
        cache = getattr(self.instance, '_prefetched_objects_cache', {})
        return relation_name in cache

    def _build_related_set_attribute(
        self,
        field_name: str,
        relation_type: str,
    ) -> RelatedSetFieldAttribute:
        """Build RelatedSetFieldAttribute for reverse FK or M2M."""
        if relation_type == 'reverse_fk':
            rel = self._get_reverse_relation(field_name)
            related_model = rel.related_model
        else:  # m2m
            field = self._get_model_field(field_name)
            related_model = field.related_model

        return RelatedSetFieldAttribute(
            owner=self,
            name=field_name,
            instance=self.instance,
            related_model=related_model,
            access=GlueAccess.VIEW,  # Read-only for v1
            is_prefetched=self._is_prefetched(field_name),
            relation_type=relation_type,
        )

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> ModelGlue:
        model_class = cast(
            'type[Model]',
            get_attr_from_path_string(policy.identity['model_class_path'])
        )

        target_pk = policy.identity.get('target_pk')
        select_related = policy.identity.get('select_related', [])
        related_field_config = policy.identity.get('related_field_config', {})

        if target_pk is None:
            instance = model_class()
        else:
            queryset = model_class.objects.all()
            if select_related:
                queryset = queryset.select_related(*select_related)
            instance = queryset.get(pk=target_pk)

        all_valid_names = set(cls._all_available_field_names_for_meta(model_class._meta))

        fields = []
        for attr in policy.attributes:
            if isinstance(attr, str):
                if attr in all_valid_names:
                    fields.append(attr)
            else:
                # Nested policy - extract field name from policy name
                # e.g., "fights.1.red_corner" -> "red_corner"
                nested_name = attr.name
                if nested_name.startswith(policy.name + '.'):
                    field_name = nested_name[len(policy.name) + 1:]
                    if field_name in all_valid_names:
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
            computed_attributes=policy.identity.get('computed_attributes', {}),
            related_field_config=related_field_config,
        )

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Apply client-provided state to the model instance."""
        self.__dict__.pop('state', None)
        self._loaded_state = state
        self._apply_state(state)

    def _apply_state(self, state: dict[str, Any]) -> None:
        """Apply state data directly to model fields."""
        for field_name in self._included_fields:
            if self._is_reverse_relation(field_name):
                continue

            field = self._get_model_field(field_name)
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

    @DeclaredAttribute(access=GlueAccess.CHANGE)
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
            if self._is_reverse_relation(field_name):
                continue

            field = self._get_model_field(field_name)
            if not getattr(field, 'many_to_many', False):
                continue
            field_state = state[field_name]
            value = field_state.get('value') if isinstance(field_state, dict) else field_state
            pks = [self._pk_from_related_value(item) for item in value or []]
            getattr(self.instance, field_name).set(pks)

    @staticmethod
    def _pk_from_related_value(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get('value')
        return getattr(value, 'pk', value)

    @DeclaredAttribute(access=GlueAccess.VIEW)
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
            choice_obj = {'pk': obj.pk, '__str__': f'{obj}'}
            for choice_field in choice_fields or []:
                choice_obj[choice_field] = getattr(obj, choice_field)
            return {
                'value': obj.pk,
                'label': f'{obj}',
                'obj': choice_obj,
            }

        return [serialize_choice(obj) for obj in related_model.objects.all()]

    # delete() only needs self.instance's pk (already resolved from the signed
    # policy identity) -- it never reads client-submitted field values. The
    # default takes_client_state=True re-hydrates every StateAttribute from
    # the client's echoed state via setattr(), including raw JS strings for
    # numeric fields (e.g. a DecimalField's <input> value). That silently
    # replaces the freshly-loaded instance's real field values with strings,
    # which then breaks any VIEW-access computed property that does
    # arithmetic on those fields once attribute collection runs for this
    # call (e.g. TypeError: unsupported operand type(s) for +: 'int' and
    # 'str' from a median_price-style property) -- a bug entirely unrelated
    # to deleting the row. takes_client_state=False skips that hydration
    # since delete has no legitimate use for it.
    @DeclaredAttribute(access=GlueAccess.DELETE, takes_client_state=False)
    def delete(self) -> None:
        self.instance.delete()

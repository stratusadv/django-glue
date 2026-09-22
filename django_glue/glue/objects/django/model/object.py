from __future__ import annotations

import base64
import json
import pickle
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Iterable, Literal, Mapping, Sequence, TypedDict, cast

from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db.models import QuerySet

from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.children import BoundGlueChild
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.computed_attributes import (
    ComputedAttribute,
    GlueComputedAttributesMixin,
)
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.field_adapter import ModelFieldAdapter
from django_glue.glue.objects.django.model_fields import ModelFieldResolutionMixin
from django_glue.glue.options.django import (
    DEFAULT_EXCLUDED_MODEL_FIELD_TYPES,
    GlueRelatedModelChoices,
    RelatedModelChoicesResult,
)
from django_glue.glue.queryset_unpickler import (
    _queryset_class_path,
    _resolve_queryset_class,
    unpickle_query,
)

# Runtime import required: Glue.Attribute method annotations are resolved with
# typing.get_type_hints() when building callable kwargs.
from django_glue.glue.policy import GluePolicy  # noqa: TC001
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django import forms
    from django.db import models
    from django.db.models import Model

ALL_FIELDS: Literal['__all__'] = '__all__'


class RelatedFieldConfig(TypedDict, total=False):
    fields: Sequence[str] | Literal['__all__']
    exclude: Sequence[str] | Literal['__all__']
    choice_queryset: QuerySet


class NormalizedRelatedFieldConfig(TypedDict, total=False):
    fields: tuple[str, ...] | Literal['__all__']
    exclude: tuple[str, ...] | Literal['__all__']
    choice_queryset: QuerySet


class RelatedFieldPolicyConfig(TypedDict, total=False):
    fields: Sequence[str] | Literal['__all__']
    exclude: Sequence[str] | Literal['__all__']
    encoded_choice_queryset: str
    choice_queryset_class_path: str


def _required_save_access(glue: ModelGlue) -> GlueAccess:
    """Saving an unsaved row requires ADD; saving a persisted row requires
    CHANGE (state-model.md §3, ADR 010).
    """
    return GlueAccess.ADD if glue.instance.pk is None else GlueAccess.CHANGE


class ModelGlue(
    GlueComputedAttributesMixin,
    ModelGlueFormConfigMixin,
    ModelFieldResolutionMixin,
    BaseGlue
):

    namespace = 'model'
    globally_excluded_field_types = DEFAULT_EXCLUDED_MODEL_FIELD_TYPES

    def __init__(
        self,
        instance: models.Model,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        editable: Sequence[str] | None = None,
        annotations: Sequence[str] = (),
        form: forms.ModelForm | None = None,
        forms: Mapping[str, forms.ModelForm] | None = None,
        select_related: Sequence[str] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, RelatedFieldConfig] | None = None,
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
        self.editable = self._normalize_editable(
            editable,
            self.access,
        )
        self.related_field_config = self._normalize_related_field_config(
            related_field_config=related_field_config,
            model_class=self.instance.__class__,
        )
        self.initialize_computed_attributes(computed_attributes)

        self.forms = self.normalize_forms(form, forms)
        self._field_errors: dict[str, list[str]] = {}
        self._editable_draft: dict[str, Any] = {}
        # Internal, signed for collection children: the access a row settles to
        # after its first save (None for top-level model bindings).
        self._row_access: GlueAccess | None = None

    def get_attribute_providers(self) -> tuple[Any, ...]:
        return (self.instance,)

    def get_identity(self) -> dict[str, Any]:
        instance = self.instance
        identity = {
            'model_class_path': f'{instance.__class__.__module__}.{instance.__class__.__name__}',
            'target_pk': instance.pk,
            'pk_field_name': instance._meta.pk.name, # type: ignore  # noqa: PGH003
            'fields': self.fields,
            'exclude': self.exclude,
            'editable': self.editable,
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self._select_related:
            identity['select_related'] = list(self._select_related)
        if self.related_field_config:
            identity['related_field_config'] = self._serialize_related_field_config(
                self.related_field_config
            )
        if self._projected_field_paths:
            identity['projected_fields'] = self._projected_field_paths
        if self._row_access is not None:
            identity['row_access'] = self._row_access
        identity |= self.computed_attributes_identity()

        return identity

    def get_extra_attributes(self) -> tuple[tuple[Any, Mapping[str, Any]], ...]:
        from django_glue import Glue  # noqa: PLC0415

        declarations = {}

        for field_name in self._included_fields:
            if self._is_reverse_relation(field_name):
                declarations[field_name] = Glue.property(
                    lambda owner, field_name=field_name: owner._get_model_attribute_value(
                        field_name
                    )
                )
                continue
            if field_name in self.editable:
                declarations[field_name] = Glue.attr(
                    property(
                        fget=lambda owner, field_name=field_name: owner._get_model_attribute_value(field_name),
                        fset=lambda owner, value, field_name=field_name: owner._stage_model_attribute_value(
                            field_name,
                            value,
                        ),
                    ),
                    required_access=GlueAccess.CHANGE,
                    editable=True,
                )
            else:
                declarations[field_name] = Glue.property(
                    lambda owner, field_name=field_name: owner._get_model_attribute_value(field_name)
                )
        for name in (*self._annotation_names, *self._computed_attribute_names):
            declarations[name] = Glue.property(
                lambda owner, name=name: owner._get_derived_attribute_value(name)
            )
        for relation_name, subfields in self._projected_relations:
            declarations[relation_name] = Glue.property(
                self._relation_child_factory(relation_name, subfields)
            )
        named_forms = tuple(
            name
            for name in self.forms
            if name != 'default'
        )
        if named_forms:
            declarations['forms'] = Glue.namespace(dict)
        for form_name in self.forms:
            path = 'form' if form_name == 'default' else f'forms.{form_name}'

            def get_form(
                owner: ModelGlue,
                form_name: str = form_name,
                path: str = path,
            ) -> FormGlue:
                return owner._build_form_child(
                    form_name=form_name,
                    path=path,
                )

            declarations[path] = Glue.property(get_form)
        return (
            (self, declarations),
        )

    def get_attribute_adapters(self) -> Mapping[str, ModelFieldAdapter]:
        return {
            field_name: ModelFieldAdapter(
                owner=self,
                name=field_name,
                field=(
                    self._get_reverse_relation(field_name)
                    if self._is_reverse_relation(field_name)
                    else self._get_model_field(field_name)
                ),
            )
            for field_name in self._included_fields
        }

    def _build_form_child(
        self,
        *,
        form_name: str,
        path: str,
    ) -> FormGlue:
        configured_form = self.forms[form_name]
        form = configured_form.__class__(
            instance=self.instance,
            initial=configured_form.initial,
        )
        return FormGlue(
            form=form,
            name=f'{self.name}.{path}',
            access=self.access,
            loading_strategy=self.resolved_loading_strategy,
        )

    def _relation_child_factory(
        self,
        relation_name: str,
        subfields: tuple[str, ...],
    ) -> Callable[[ModelGlue], BaseGlue | None]:
        """Return a child-producing factory for a projected relation.

        The return annotation is normalized to match the relation's
        nullability: a nullable foreign key yields a nullable child slot that
        is re-evaluated on every owner interaction, while a non-nullable one
        is never evaluated to discover it still exists (state-model.md §4).
        """
        from django_glue.glue.objects.django.queryset import QuerySetGlue  # noqa: PLC0415

        nullable = self._relation_is_nullable(relation_name)
        child_type = (
            QuerySetGlue
            if self._relation_is_to_many(relation_name)
            else ModelGlue
        )

        def get_relation(owner: ModelGlue) -> BaseGlue | None:
            return owner._build_relation_child(relation_name, subfields)

        get_relation.__annotations__ = {
            'owner': ModelGlue,
            'return': child_type | None if nullable else child_type,
        }
        return get_relation

    def _build_relation_child(
        self,
        relation_name: str,
        subfields: tuple[str, ...],
    ) -> BaseGlue | None:
        if self._relation_is_to_many(relation_name):
            if self.instance.pk is None:
                field = self._get_model_field(relation_name)
                related = field.related_model._default_manager.none()
            else:
                related = getattr(self.instance, relation_name).all()
        else:
            try:
                related = getattr(self.instance, relation_name)
            except ObjectDoesNotExist:
                return None
        if related is None:
            return None
        return self._construct_relation_child(
            related,
            name=f'{self.name}.{relation_name}',
            subfields=subfields,
        )

    def _get_model_attribute_value(self, field_name: str) -> Any:
        if field_name in self._editable_draft:
            return self._editable_draft[field_name]
        relation_name = (
            field_name[:-4]
            if field_name.endswith('_ids')
            else field_name
        )
        if self._relation_is_to_many(relation_name):
            if self.instance.pk is None:
                return ()
            return tuple(
                getattr(self.instance, relation_name).values_list(
                    'pk',
                    flat=True,
                )
            )
        field = self._get_model_field(field_name)
        return getattr(self.instance, field.attname)

    def _stage_model_attribute_value(
        self,
        field_name: str,
        value: Any,
    ) -> None:
        field = self._get_model_field(field_name)
        if getattr(field, 'get_internal_type', lambda: '')() in {'FileField', 'ImageField'}:
            return
        self._editable_draft[field_name] = value

    def _retained_state(self) -> dict[str, Any]:
        """The snapshot carries a complete baseline: the overlay resolves to
        the row's current value on every exposed editable path, so the
        client's canonical view is complete from the token alone
        (state-model.md §4)."""
        retained = super()._retained_state()
        retained.update({
            field_name: self._get_model_attribute_value(field_name)
            for field_name in self.editable
        })
        return retained

    def _get_derived_attribute_value(self, name: str) -> Any:
        if name in self.computed_attributes:
            return self.computed_attribute_values(self.instance)[name]
        return getattr(self.instance, name)

    @cached_property
    def _annotation_names(self) -> tuple[str, ...]:
        return tuple(self.annotations)

    @staticmethod
    def _normalize_related_field_config(
        related_field_config: Mapping[str, RelatedFieldConfig] | None,
        model_class: type[Model],
    ) -> dict[str, NormalizedRelatedFieldConfig]:
        normalized: dict[str, NormalizedRelatedFieldConfig] = {}
        for field_name, config in (related_field_config or {}).items():
            # Every key must name a relation on the model -- related_field_config
            # only ever configures related objects, so a non-relation (or typo'd)
            # key is a mistake worth surfacing rather than silently dropping.
            try:
                related_field = model_class._meta.get_field(field_name)
            except FieldDoesNotExist as exception:
                msg = f'related_field_config contains an unknown field: {field_name!r}.'
                raise ValueError(msg) from exception
            related_model = getattr(related_field, 'related_model', None)
            if related_model is None:
                msg = f'related_field_config field {field_name!r} is not a relation.'
                raise ValueError(msg)

            normalized_config = NormalizedRelatedFieldConfig()
            fields = config.get('fields')
            if fields:
                normalized_config['fields'] = (
                    fields if fields == ALL_FIELDS else tuple(fields)
                )
            exclude = config.get('exclude')
            if exclude:
                normalized_config['exclude'] = (
                    exclude if exclude == ALL_FIELDS else tuple(exclude)
                )
            choice_queryset = config.get('choice_queryset')
            if choice_queryset is not None:
                if not isinstance(choice_queryset, QuerySet):
                    msg = (
                        f'related_field_config[{field_name!r}].choice_queryset '
                        'must be a QuerySet.'
                    )
                    raise TypeError(msg)
                if choice_queryset.model is not related_model:
                    msg = (
                        f'related_field_config[{field_name!r}].choice_queryset must query '
                        f'{related_model._meta.label}, not {choice_queryset.model._meta.label}.'
                    )
                    raise ValueError(msg)
                normalized_config['choice_queryset'] = choice_queryset.all()
            normalized[field_name] = normalized_config
        return normalized

    @staticmethod
    def _serialize_related_field_config(
        related_field_config: Mapping[str, NormalizedRelatedFieldConfig],
    ) -> dict[str, RelatedFieldPolicyConfig]:
        serialized: dict[str, RelatedFieldPolicyConfig] = {}
        for field_name, config in related_field_config.items():
            serialized_config = RelatedFieldPolicyConfig()
            fields = config.get('fields')
            if fields:
                serialized_config['fields'] = fields
            exclude = config.get('exclude')
            if exclude:
                serialized_config['exclude'] = exclude
            choice_queryset = config.get('choice_queryset')
            if choice_queryset is not None:
                serialized_config['encoded_choice_queryset'] = base64.b64encode(
                    pickle.dumps(choice_queryset.query)
                ).decode('utf-8')
                serialized_config['choice_queryset_class_path'] = (
                    _queryset_class_path(choice_queryset)
                )
            serialized[field_name] = serialized_config
        return serialized

    @staticmethod
    def _deserialize_related_field_config(
        related_field_config: Mapping[str, RelatedFieldPolicyConfig],
    ) -> dict[str, NormalizedRelatedFieldConfig]:
        # The exact inverse of _serialize_related_field_config: the policy is
        # signed, so its contents are already validated -- reconstruct the
        # normalized internal shape directly, no re-validation needed.
        deserialized: dict[str, NormalizedRelatedFieldConfig] = {}
        for field_name, config in related_field_config.items():
            deserialized_config = NormalizedRelatedFieldConfig()
            fields = config.get('fields')
            if fields:
                deserialized_config['fields'] = (
                    fields if fields == ALL_FIELDS else tuple(fields)
                )
            exclude = config.get('exclude')
            if exclude:
                deserialized_config['exclude'] = (
                    exclude if exclude == ALL_FIELDS else tuple(exclude)
                )
            encoded_queryset = config.get('encoded_choice_queryset')
            if encoded_queryset is not None:
                query = unpickle_query(encoded_queryset)
                choice_queryset = _resolve_queryset_class(
                    config.get('choice_queryset_class_path')
                )(model=query.model)
                choice_queryset.query = query
                deserialized_config['choice_queryset'] = choice_queryset
            deserialized[field_name] = deserialized_config
        return deserialized

    @property
    def _model_meta(self) -> Any:
        """Return the Django model's _meta options."""
        return self.instance._meta

    def get_state(self) -> dict[str, Any]:
        self.hydrate_computed_attributes(self.instance)
        self._validate()
        return super().get_state()

    def _validate(self) -> None:
        if (
            not self._editable_draft
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

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> ModelGlue:
        model_class = cast(
            'type[Model]',
            get_attr_from_path_string(policy.identity['model_class_path'])
        )

        target_pk = policy.identity.get('target_pk')
        select_related = policy.identity.get('select_related', [])
        # Collection children sign the access their row settles to. A draft
        # (target_pk None) requires ADD until its first save; a persisted row
        # takes the signed row access. Top-level model bindings have no
        # row_access and keep their registered policy access (state-model.md
        # §3, ADR 010). Identity values are JSON round-tripped, so the signed
        # row_access must be coerced back to a GlueAccess.
        raw_row_access = policy.identity.get('row_access')
        if raw_row_access is not None:
            row_access = GlueAccess(raw_row_access)
            restored_access = GlueAccess.ADD if target_pk is None else row_access
        else:
            row_access = None
            restored_access = policy.access

        if target_pk is None:
            instance = model_class()
        else:
            queryset = model_class.objects.all()
            if select_related:
                queryset = queryset.select_related(*select_related)
            instance = queryset.get(pk=target_pk)

        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {}),
            instance=instance
        )

        glue_object = cls(
            instance,
            name=policy.name,
            access=restored_access,
            fields=policy.identity['fields'],
            exclude=policy.identity['exclude'],
            editable=policy.identity['editable'],
            forms=forms,
            select_related=select_related,
            computed_attributes=policy.identity.get('computed_attributes', {}),
        )
        glue_object._row_access = row_access
        if row_access is not None:
            glue_object._signed_row_children = policy.children
        # Restored post-construction from the signed (already-validated) policy:
        # _deserialize_related_field_config yields the normalized internal shape,
        # so it does not go back through __init__ normalization.
        glue_object.related_field_config = cls._deserialize_related_field_config(
            policy.identity.get('related_field_config', {})
        )
        return glue_object

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        """Bind children, restoring signed collection-owned relation
        references for reconstructed collection rows (state-model.md §4).

        A collection row never owns its projected relation children; the
        collection does. Re-deriving them from the row would address them
        beneath the row instead of the collection and reintroduce duplicate
        proxies, so the references the row policy signed at introduction
        stand as its prior child state. Non-relation children (e.g. forms)
        re-derive normally."""
        bound_children = super()._bind_children(
            live_children=live_children,
            reintroduce=reintroduce,
        )
        signed_children = getattr(self, '_signed_row_children', None)
        if self._row_access is None or not signed_children:
            return bound_children
        relation_paths = {
            relation_name
            for relation_name, _subfields in self._projected_relations
        }
        return tuple(
            BoundGlueChild(path=child.path, address=signed_children[child.path])
            if child.path in relation_paths and child.path in signed_children
            else child
            for child in bound_children
        )

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Admit acknowledged edits into the editable draft, then apply the
        draft to the instance for editing (state-model.md §4). The re-fetched
        row is the baseline, so only values that differ from it enter the
        draft."""
        self._invalidate_state()
        super()._load_client_state(
            {
                path: value
                for path, value in state.items()
                if path not in self.editable or not self._matches_row_value(path, value)
            }
        )
        self._apply_draft_to_instance()
        self._apply_file_fields()

    def _matches_row_value(self, field_name: str, value: Any) -> bool:
        """Whether a signed value still equals the row's current value,
        normalized the way token payloads JSON round-trip."""
        current = self._get_model_attribute_value(field_name)
        return json.loads(json.dumps(value, cls=GlueResponseJSONEncoder)) == json.loads(
            json.dumps(current, cls=GlueResponseJSONEncoder)
        )

    def _apply_draft_to_instance(self) -> None:
        """Apply the admitted draft to the instance. M2M membership is
        deferred to save(), where the instance has a pk to attach it to."""
        for field_name, value in self._editable_draft.items():
            field = self._get_model_field(field_name)
            if getattr(field, 'many_to_many', False):
                continue
            if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                setattr(self.instance, field.attname, value)
                continue
            setattr(self.instance, field_name, value)

    def _apply_file_fields(self) -> None:
        for field_name in self.editable:
            field = self._get_model_field(field_name)
            if getattr(field, 'get_internal_type', lambda: '')() not in {'FileField', 'ImageField'}:
                continue
            file_value = self._get_file_from_request(field_name)
            if file_value is not None:
                setattr(self.instance, field_name, file_value)

    def _get_file_from_request(self, field_name: str) -> Any:
        """Get a file from request.FILES for a field."""
        if not self.request or not self.request.FILES:
            return None

        return self.request.FILES.get(field_name)

    @DeclaredAttribute(required_access=_required_save_access)
    def save(self) -> dict[str, Any]:
        try:
            self.instance.full_clean()
            self.instance.save()
            self._apply_m2m_state(self._editable_draft)
            self._rebase_draft()
            # A collection draft settles to its signed row access on first save:
            # this re-signs the successor response at the settled access, so the
            # client's next request carries the persisted-row permission
            # (state-model.md ADR 010).
            if self._row_access is not None:
                self.access = self._row_access
            self._field_errors = {}
            self._derived_paths.update(self._included_fields)
            return {  # noqa: TRY300
                'success': True,
                'errors': {}
            }
        except ValidationError as e:
            self._field_errors = (
                e.message_dict if hasattr(e, 'message_dict') else {'__all__': e.messages}
            )
            self._derived_paths.update(self._included_fields)
            return {
                'success': False,
                'errors': self._field_errors
            }

    def _apply_m2m_state(self, state: dict[str, Any]) -> None:
        """Apply M2M field values after the instance has been saved."""
        for field_name in self.editable:
            if field_name not in state:
                continue
            field = self._get_model_field(field_name)
            if not getattr(field, 'many_to_many', False):
                continue
            pks = [
                self._pk_from_related_value(item)
                for item in state[field_name] or []
            ]
            getattr(self.instance, field_name).set(pks)

    def _rebase_draft(self) -> None:
        """Rebase the draft onto the values the saved instance now holds
        (state-model.md §4)."""
        for field_name in tuple(self._editable_draft):
            field = self._get_model_field(field_name)
            if getattr(field, 'many_to_many', False):
                self._editable_draft[field_name] = tuple(
                    getattr(self.instance, field_name).values_list('pk', flat=True)
                )
            elif getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
                self._editable_draft[field_name] = getattr(self.instance, field.attname)
            else:
                self._editable_draft[field_name] = getattr(self.instance, field_name)

    @staticmethod
    def _pk_from_related_value(value: Any) -> Any:
        if isinstance(value, dict):
            return value.get('value')
        return getattr(value, 'pk', value)

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def foreign_key_choices(
        self,
        field_name: str | None = None,
        search: str = '',
    ) -> RelatedModelChoicesResult:
        projected_relations = {
            relation_name for relation_name, _subfields in self._projected_relations
        }
        if not field_name or (
            field_name not in self._included_fields
            and field_name not in projected_relations
        ):
            return GlueRelatedModelChoices.empty()

        queryset = self._choice_queryset_for_field(field_name)
        if queryset is None:
            return GlueRelatedModelChoices.empty()

        return GlueRelatedModelChoices(
            queryset,
            value_field_name=self._choice_value_field_name_for_field(field_name),
        ).load(
            search=search,
        )

    def _choice_value_field_name_for_field(self, field_name: str) -> str:
        field = self.instance._meta.get_field(field_name)
        target_field = getattr(field, 'target_field', None)
        if target_field is not None:
            return target_field.name
        return field.related_model._meta.pk.name

    def _choice_queryset_for_field(self, field_name: str) -> QuerySet | None:
        field = self.instance._meta.get_field(field_name)
        related_model = getattr(field, 'related_model', None)
        if related_model is None:
            return None
        configured_queryset = self.related_field_config.get(field_name, {}).get(
            'choice_queryset'
        )
        if configured_queryset is not None:
            return configured_queryset
        return related_model.objects.all()

    @DeclaredAttribute(required_access=GlueAccess.DELETE)
    def delete(self) -> None:
        self.instance.delete()
        self.dispose()

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

from django import forms
from django.db.models import QuerySet
from django.forms.models import model_to_dict

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.field_adapter import FormFieldAdapter
from django_glue.glue.options.django import (
    GlueRelatedModelChoices,
    RelatedModelChoicesResult,
)
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django.db.models import Model

    from django_glue.glue.policy import GluePolicy


def _required_save_access(glue: FormGlue) -> GlueAccess:
    """Saving an unsaved instance requires ADD; a persisted target requires
    CHANGE (state-model.md §3, ADR 010). A plain form has no instance, so it
    is always create-only.
    """
    instance = getattr(glue.form, 'instance', None)
    if instance is None or instance.pk is None:
        return GlueAccess.ADD
    return GlueAccess.CHANGE


class FormGlue(BaseGlue):
    namespace = 'form'

    def __init__(
        self,
        form: forms.BaseForm,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        editable: Sequence[str] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.form = form
        self.editable = self._normalize_editable(editable)
        self._loaded_state: dict[str, Any] | None = None
        self._field_errors: dict[str, list[str]] = {}
        self._editable_draft: dict[str, Any] = {}
        self._bound_form: forms.BaseForm | None = None

    def get_attribute_providers(self) -> tuple[Any, ...]:
        return (self.form,)

    def get_identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.form.__class__.__module__}.{self.form.__class__.__name__}',
            'target_pk': getattr(getattr(self.form, 'instance', None), 'pk', None),
            'initial': self._prepared_initial,
            'editable': self.editable,
        }

    def _normalize_editable(
        self,
        editable: Sequence[str] | None,
    ) -> tuple[str, ...]:
        if editable is None:
            selected = tuple(
                name
                for name, field in self.form.fields.items()
                if not field.disabled
            )
        else:
            selected = tuple(dict.fromkeys(editable))
            unknown = tuple(
                name
                for name in selected
                if name not in self.form.fields
            )
            if unknown:
                msg = f'Editable form fields must be exposed: {unknown!r}.'
                raise ValueError(msg)
            disabled = tuple(
                name
                for name in selected
                if self.form.fields[name].disabled
            )
            if disabled:
                msg = f'Disabled form fields cannot be editable: {disabled!r}.'
                raise ValueError(msg)

        if not self.access.has_access(GlueAccess.ADD):
            return ()
        return selected

    def get_extra_attributes(self) -> tuple[tuple[Any, Mapping[str, Any]], ...]:
        from django_glue import Glue  # noqa: PLC0415

        declarations = {}
        for name in self.form.fields:
            if name in self.editable:
                declarations[name] = Glue.attr(
                    property(
                        fget=lambda owner, name=name: owner._get_form_attribute_value(name),
                        fset=lambda owner, value, name=name: owner._stage_form_attribute_value(
                            name,
                            value,
                        ),
                    ),
                    required_access=GlueAccess.CHANGE,
                    editable=True,
                )
            else:
                declarations[name] = Glue.property(
                    lambda owner, name=name: owner._get_form_attribute_value(name)
                )
        return (
            (self, declarations),
        )

    def get_attribute_adapters(self) -> Mapping[str, FormFieldAdapter]:
        return {
            name: FormFieldAdapter(
                owner=self,
                name=name,
                field=field,
            )
            for name, field in self.form.fields.items()
        }

    def _get_form_attribute_value(self, name: str) -> Any:
        if name in self._editable_draft:
            return self._editable_draft[name]
        return self.form[name].value()

    def _stage_form_attribute_value(
        self,
        name: str,
        value: Any,
    ) -> None:
        self._editable_draft[name] = value

    @property
    def _prepared_initial(self) -> dict[str, Any]:
        return {
            name: field.prepare_value(self._ordered(value)) if field else value
            for name, value in self.form.initial.items()
            for field in [self.form.fields.get(name)]
        }

    @staticmethod
    def _ordered(value: Any) -> Any:
        """Return `value` with a deterministic iteration order.

        A ManyToMany (or other unordered) queryset has no guaranteed row order, so two
        evaluations of the "same" relation can iterate in a different order even though
        the underlying data hasn't changed. That's fatal here: this value feeds a signed
        GluePolicy, and a reordering alone would change the serialized bytes and therefore
        the signature, producing a spurious "policy has been tampered with" error. Sorting
        by pk before `field.prepare_value()` sees it removes that nondeterminism regardless
        of what prepare_value does with the value (return model instances, pks, etc).
        """
        if isinstance(value, (QuerySet, list, tuple, set, frozenset)):
            try:
                return sorted(value, key=lambda item: getattr(item, 'pk', item))
            except TypeError:
                return value
        return value

    def get_state(self) -> dict[str, Any]:
        self._populate_field_errors()
        return super().get_state()

    def _populate_field_errors(self) -> None:
        """Populate _field_errors from form errors."""
        self._field_errors = dict(self.form.errors)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormGlue:
        form_class = get_attr_from_path_string(policy.identity['form_class_path'])
        initial = policy.identity.get('initial', {})
        target_pk = policy.identity.get('target_pk')

        if issubclass(form_class, forms.ModelForm):
            model_class = form_class._meta.model

            if target_pk is not None:
                try:
                    instance = model_class.objects.get(pk=target_pk)
                    model_initial = model_to_dict(
                        instance,
                        form_class._meta.fields,
                        form_class._meta.exclude,
                    )
                    initial = {**model_initial, **initial}
                    form = form_class(instance=instance, initial=initial)
                except model_class.DoesNotExist:
                    form = form_class(initial=initial)
            else:
                # No target_pk means this form was never saved (e.g. built
                # via QuerySetGlue.new()/ModelGlue on an unsaved instance).
                # `initial` only pre-fills displayed widget values though --
                # it never touches self.instance -- so without this, a form
                # method that reads self.instance.<field> (e.g. to narrow a
                # dependent queryset the same way a bound instance would)
                # silently sees an empty instance instead of what the
                # client is about to submit. Rebuild the same unsaved
                # instance QuerySetGlue.new() would have built, so
                # self.instance stays consistent across every place a form
                # for this same not-yet-saved row gets reconstructed.
                form = form_class(instance=cls._unsaved_instance_from_initial(model_class, initial), initial=initial)
        else:
            form = form_class(initial=initial)

        return cls(
            form,
            name=policy.name,
            access=policy.access,
            editable=policy.identity['editable'],
        )

    @staticmethod
    def _unsaved_instance_from_initial(model_class: type[Model], initial: dict[str, Any]) -> Model:
        model_fields = {field.name: field for field in model_class._meta.get_fields()}
        field_kwargs = {}

        for name, value in initial.items():
            model_field = model_fields.get(name)
            # Skip anything that isn't a concrete, single-valued model field
            # (reverse relations, generic FKs) and many-to-many fields --
            # M2M can't be set via the model constructor at all (it needs a
            # saved pk first), and initial's prepared value for one is a
            # list of pks anyway, not a single scalar.
            if (
                model_field is None
                or value is None
                or getattr(model_field, 'many_to_many', False)
                or not getattr(model_field, 'concrete', False)
            ):
                continue
            attname = getattr(model_field, 'attname', name)
            field_kwargs[attname] = value

        return model_class(**field_kwargs)

    def _load_client_state(self, state: dict[str, Any]) -> None:
        """Bind client-provided state before executing form attributes."""
        self._loaded_state = {
            name: value
            for name, value in state.items()
            if name in self.editable
        }
        self.form = self._bind_form()

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def validate(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        self._bound_form = bound_form
        return {'valid': bound_form.is_valid(), 'errors': dict(bound_form.errors)}

    @DeclaredAttribute(required_access=_required_save_access)
    def save(self) -> dict[str, Any]:
        bound_form = self._bind_form()
        valid = bound_form.is_valid()
        if valid and hasattr(bound_form, 'save'):
            bound_form.save()
        return {'valid': valid, 'errors': dict(bound_form.errors)}

    # Choice loading is read-only; returning form state would trigger validation during serialization.
    @DeclaredAttribute(required_access=GlueAccess.VIEW, takes_client_state=False, updates_client_state=False)
    def foreign_key_choices(
        self,
        field_name: str | None = None,
        search: str = '',
    ) -> RelatedModelChoicesResult:
        if not field_name or field_name not in self.form.fields:
            return GlueRelatedModelChoices.empty()

        field = self.form.fields[field_name]
        queryset = getattr(field, 'queryset', None)
        if queryset is None:
            return GlueRelatedModelChoices.empty()

        return GlueRelatedModelChoices(
            queryset,
            value_field_name=getattr(field, 'to_field_name', None),
        ).load(
            search=search,
        )

    def _bind_form(self) -> forms.BaseForm:
        state = self._loaded_state or {}
        form_class = self.form.__class__
        # Extract values from new state structure: {field_name: {value: ..., errors: ...}}
        data = {}
        for field_name in self.form.fields:
            field_state = state.get(field_name, self.form[field_name].value())
            data[field_name] = (
                field_state.get('value')
                if isinstance(field_state, dict)
                else field_state
            )
        kwargs = {
            'data': data,
            'files': self.request.FILES if self.request else None,
        }
        has_instance = getattr(self.form, 'instance', None) is not None
        if isinstance(self.form, forms.ModelForm) and has_instance:
            kwargs['instance'] = self.form.instance
        return form_class(**kwargs)

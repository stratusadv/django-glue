from __future__ import annotations

import hashlib
from typing import Any, Mapping, TYPE_CHECKING

from django.db import transaction
from django.forms import BaseForm, ModelForm

from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueAccessError,
    GlueFormSetMaxNumExceededError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.collection import BaseCollectionGlue
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.policy import GluePolicy, GluePolicyTokenSerializer
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from django import forms
    from django.db.models import Model, QuerySet

    from django_glue.glue.base import BaseGlue


def _row_binding(identity: Mapping[str, Any], access: GlueAccess) -> str:
    """
    A digest of what a row's token signs about it: its form class, record,
    initial values, editable fields and access. The formset signs one per row,
    so a row token is only accepted by the formset that issued it. Serialized
    as tokens are, so a row reads the same before and after it is signed.
    """
    payload = GluePolicyTokenSerializer().dumps({'identity': identity, 'access': access})
    return hashlib.blake2s(payload, digest_size=8).hexdigest()


class FormSetGlue(BaseCollectionGlue):
    """A keyed collection of ``FormGlue`` children sharing a single form class.

    Replaces the legacy ``BaseFormSet`` substrate (ADR 012). The formset owns
    the order/membership (the keys) and the formset-level concerns; per-form
    work is delegated to the ``FormGlue`` children. The collection starts
    empty unless seeded with ``instances`` (saved model rows to edit, for a
    ``ModelForm``) and/or ``initial`` (one dict per prefilled blank row) --
    ``min_num`` / ``max_num`` are validation floors/ceilings, not a
    "spawn N blank forms" count. Application code subclasses ``Glue.FormSet``
    and optionally overrides ``clean()`` for cross-form validation; it never
    sees a ``FormGlue``.
    """

    namespace = 'formSet'

    form_class: type[forms.BaseForm] | None = None
    min_num: int = 0
    max_num: int | None = None
    can_delete: bool = False

    def __init__(
        self,
        form_class: type[forms.BaseForm] | None = None,
        *,
        initial: Iterable[Mapping[str, Any]] = (),
        instances: Iterable[Model | forms.BaseForm] = (),
        new_row_defaults: Mapping[str, Any] | None = None,
        name: str | None = None,
        access: GlueAccess = GlueAccess.CHANGE,
        min_num: int | None = None,
        max_num: int | None = None,
        can_delete: bool | None = None,
        _reconstructed: bool = False,
    ) -> None:
        super().__init__(name=name, access=access)
        cls = self.__class__
        self.form_class = form_class if form_class is not None else cls.form_class

        if self.form_class is None:
            msg = f"FormSetGlue '{name}' requires a form_class."
            raise ValueError(msg)

        self.min_num = cls.min_num if min_num is None else min_num
        self.max_num = cls.max_num if max_num is None else max_num
        self.can_delete = cls.can_delete if can_delete is None else can_delete
        self.new_row_defaults = dict(new_row_defaults or {})
        self._live_children: dict[str, str] = {}
        self._removed_pks: list[Any] = []
        # None on a formset rebuilt from a token issued before rows were bound.
        self._row_bindings: dict[str, str] | None = {}
        self._reconstructed = _reconstructed

        initial_forms: list[forms.BaseForm] = []
        for instance in instances:
            if isinstance(instance, BaseForm):
                self._validate_initial_form(instance)
                if getattr(getattr(instance, 'instance', None), 'pk', None) is None:
                    # A supplied form with no saved record is a new row like any other.
                    instance.initial = {**instance.initial, **self.new_row_defaults}
                initial_forms.append(instance)
            else:
                self._validate_initial_model_instance(instance)
                initial_forms.append(self.form_class(instance=instance))

        for row_initial in initial:
            if not isinstance(row_initial, Mapping):
                msg = (
                    f"FormSetGlue '{name}' initial must be a list of dicts, not "
                    f'{row_initial.__class__.__qualname__}.'
                )
                raise TypeError(msg)
            initial_forms.append(
                self.form_class(initial={**row_initial, **self.new_row_defaults}),
            )

        self._forms: list[tuple[str, FormGlue]] = []
        for index, form in enumerate(initial_forms):
            self._add_form(form, str(index))

    def _add_form(self, form: forms.BaseForm, key: str) -> FormGlue:
        """
        Admit one row under ``key``. The single path by which a form joins
        the collection, so seeded and appended rows obey the same rules.
        """
        if key in self._live_children or any(existing == key for existing, _ in self._forms):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Formset row key is already in use.',
            )

        count = len(set(self._live_children) | {row_key for row_key, _ in self._forms})

        if self.max_num is not None and count >= self.max_num:
            raise GlueFormSetMaxNumExceededError(count, self.max_num)

        form_glue = self._build_form_glue(form, key)
        self._forms.append((key, form_glue))

        return form_glue

    def _validate_initial_form(self, form: forms.BaseForm) -> None:
        if type(form) is not self.form_class:
            msg = (
                f"FormSetGlue '{self.name}' forms must be {self.form_class.__qualname__} "
                f'forms, not {form.__class__.__qualname__}.'
            )
            raise TypeError(msg)

        if form.is_bound:
            msg = (
                f"FormSetGlue '{self.name}' initial forms must be unbound; pass values "
                'through initial= or instance=, not data=.'
            )
            raise ValueError(msg)

    def _validate_initial_model_instance(self, instance: Model) -> None:
        if not issubclass(self.form_class, ModelForm):
            msg = (
                f"FormSetGlue '{self.name}' instances must be {self.form_class.__qualname__} "
                f'forms, not {instance.__class__.__qualname__}: its form_class is not a '
                'ModelForm, so it cannot wrap a model instance.'
            )
            raise TypeError(msg)

        model_class = self.form_class._meta.model
        if not isinstance(instance, model_class):
            msg = (
                f"FormSetGlue '{self.name}' instances must be {model_class.__qualname__} "
                f'objects or {self.form_class.__qualname__} forms, not '
                f'{instance.__class__.__qualname__}.'
            )
            raise TypeError(msg)

        if instance.pk is None:
            msg = (
                f"FormSetGlue '{self.name}' instances must be saved; an unsaved "
                f'{model_class.__qualname__} would be created instead of edited.'
            )
            raise ValueError(msg)

    def get_identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.form_class.__module__}.{self.form_class.__qualname__}',
            'formset_class_path': f'{self.__class__.__module__}.{self.__class__.__qualname__}',
            'min_num': self.min_num,
            'max_num': self.max_num,
            'can_delete': self.can_delete,
            'new_row_defaults': self.new_row_defaults,
        }

    def get_keyed_items(self) -> list[tuple[str, BaseGlue]]:
        return list(self._forms)

    def _membership(
        self,
        live_children: Mapping[str, str],
        produced: Mapping[str, BaseGlue],
    ) -> list[str]:
        return [
            *(key for key in live_children if key in self._live_children),
            *(key for key in produced if key not in live_children),
        ]

    def get_state(self) -> dict[str, Any]:
        return {'forms': {key: form.state for key, form in self._forms}}

    def _get_retained_state(self) -> dict[str, Any]:
        """
        Records removed by ``pop`` stay signed until ``save`` deletes them: the
        removal and the save are separate requests. Each live row's binding is
        signed too: a row this request did not rebuild keeps the one it had.
        """
        retained = super()._get_retained_state()
        if self._removed_pks:
            retained['removed_pks'] = list(self._removed_pks)
        if self._row_bindings is not None:
            retained['row_bindings'] = {
                **{
                    key: binding
                    for key, binding in self._row_bindings.items()
                    if key in self._live_children
                },
                **{key: _row_binding(form.get_identity(), form.access) for key, form in self._forms},
            }
        return retained

    def clean(self, form_list: list[forms.BaseForm]) -> list[str]:  # noqa: ARG002
        """Cross-form validation hook. Override to add formset-level errors.

        Receives the plain, already-validated Django ``Form``s (never
        ``FormGlue``s) so application code stays Django-idiomatic.
        """
        return []

    def save_forms(self, form_list: list[forms.BaseForm]) -> None:
        """
        Save hook, run by ``save()`` inside its transaction. Receives the
        validated Django forms of the remaining rows; override to save them
        another way. A saved record whose form has not changed is not written.
        """
        for form in form_list:
            if not hasattr(form, 'save'):
                continue
            instance = getattr(form, 'instance', None)
            is_saved_record = instance is not None and instance.pk is not None
            if not is_saved_record or form.has_changed():
                form.save()

    def delete_removed(self, queryset: QuerySet) -> None:
        """
        Deletion hook, run by ``save()`` inside its transaction. Receives the
        saved records whose rows were removed; override to soft-delete.
        """
        queryset.delete()

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def append(self, key: str, initial: dict[str, Any] | None = None) -> FormGlue:
        """
        ``initial`` comes from the client, so it may only prefill fields the
        form lets a user edit. ``new_row_defaults`` come from the server, are
        applied over it, and may set fields the form does not expose.
        """
        initial = initial or {}
        editable = {
            name for name, field in self.form_class.base_fields.items() if not field.disabled
        }
        if not isinstance(initial, Mapping) or not set(initial) <= editable:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Initial values may only name editable form fields.',
                details={
                    'fields': sorted(set(initial) - editable) if isinstance(initial, Mapping) else [],
                },
            )

        return self._add_form(
            self.form_class(initial={**initial, **self.new_row_defaults}),
            key,
        )

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def pop(self, key: str) -> None:
        if not self.can_delete:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='This formset does not allow row removal.',
            )

        rows = dict(self._forms)
        if key not in self._live_children or key not in rows:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Formset row key is not live.',
            )

        target_pk = rows[key].get_identity()['target_pk']
        if target_pk is not None:
            if not self.access.has_access(GlueAccess.DELETE):
                raise GlueAccessError(
                    attribute='pop',
                    required_access=GlueAccess.DELETE.value,
                    current_access=self.access.value,
                )
            self._removed_pks.append(target_pk)

        del self._live_children[key]
        self._forms = [(row_key, form) for row_key, form in self._forms if row_key != key]

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def validate(self) -> dict[str, Any]:
        form_glues = [form for _, form in self._forms]
        per_form = [form.validate() for form in form_glues]
        bound_forms = [form.bound_form for form in form_glues]
        count = len(self._forms)
        cardinality_errors = []
        if count < self.min_num:
            cardinality_errors.append(f'Please submit at least {self.min_num} form(s).')
        if self.max_num is not None and count > self.max_num:
            cardinality_errors.append(f'Please submit at most {self.max_num} form(s).')
        non_form_errors = [*cardinality_errors, *self.clean(bound_forms)]
        valid = all(result['valid'] for result in per_form) and not non_form_errors
        return {
            'valid': valid,
            'form_list': form_glues,
            'non_form_errors': non_form_errors,
        }

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def save(self) -> dict[str, Any]:
        form_glues = [form for _, form in self._forms]
        results = [form.validate() for form in form_glues]
        if not all(result['valid'] for result in results):
            return {'valid': False}

        with transaction.atomic():
            self.save_forms([form.bound_form for form in form_glues])
            if self._removed_pks:
                model = self.form_class._meta.model
                self.delete_removed(model._default_manager.filter(pk__in=self._removed_pks))

        self._removed_pks = []
        return {'valid': True}

    def _build_form_glue(self, form: forms.BaseForm, key: str) -> FormGlue:
        return FormGlue(form, name=f'{self.name}.{key}', access=self.access)

    def _load_client_state(self, state: dict[str, Any]) -> None:
        if 'forms' not in state:
            return

        form_state_entries = state.get('forms') or {}

        self._forms = []
        for key, form_state in form_state_entries.items():
            form_glue = self._build_form_glue(self.form_class(initial={}), key)
            form_glue._load_client_state(form_state)
            self._forms.append((key, form_glue))

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        kwargs = dict(call_context.target_attribute_call_kwargs)
        submitted = kwargs.pop('__submitted_forms', None)
        attribute = call_context.target_attribute_name

        if attribute == 'pop':
            popped_key = kwargs.get('key')
            if isinstance(popped_key, str) and popped_key in self._live_children:
                self._hydrate_submitted_forms(call_context, submitted, [popped_key])
        elif submitted is not None:
            self._hydrate_submitted_forms(call_context, submitted, self._live_children)
        elif self._live_children and attribute != 'append':
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Every live formset row must be submitted with its signed form token.',
            )

        entry, introduced = super().process_attribute_call(
            call_context.model_copy(update={'target_attribute_call_kwargs': kwargs}),
        )
        if submitted is not None:
            introduced.extend(form.entry.model_dump() for _, form in self._forms)
        return entry, introduced

    def _run_call(
        self,
        call_context: AttributeCallRequestContext,
        invoke: Callable[[], Any],
        *,
        render_as_html: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        ``validate()`` returns its row forms to Python callers. On the wire a
        row is its address, and a result may not carry a Glue object.
        """
        def invoke_for_wire() -> Any:
            result = invoke()
            if call_context.target_attribute_name == 'validate':
                return {**result, 'form_list': [form.address for form in result['form_list']]}
            return result

        return super()._run_call(call_context, invoke_for_wire, render_as_html=render_as_html)

    def _hydrate_submitted_forms(
        self,
        call_context: AttributeCallRequestContext,
        submitted: Any,
        keys: Iterable[str],
    ) -> None:
        if not isinstance(submitted, dict) or set(submitted) != set(keys):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Submitted formset rows must match signed membership.',
            )

        child_contexts: dict[str, AttributeCallRequestContext] = {}
        for key in keys:
            data = submitted[key]
            if not isinstance(data, dict) or not isinstance(data.get('policy_token'), str):
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='A formset row needs its signed form token.',
                )
            child_policy = GluePolicy.from_token(data['policy_token'])
            if (
                child_policy.address != self._live_children[key]
                or child_policy.namespace != 'form'
                or child_policy.name != f'{self.name}.{key}'
                or child_policy.identity.get('form_class_path') != self.identity['form_class_path']
                or child_policy.session_id != call_context.target_glue_policy.session_id
                or child_policy.request_user_id != call_context.target_glue_policy.request_user_id
                or (
                    self._row_bindings is not None
                    and self._row_bindings.get(key) != _row_binding(child_policy.identity, child_policy.access)
                )
            ):
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='Submitted form token does not belong to this formset row.',
                )
            child_contexts[key] = AttributeCallRequestContext.model_construct(
                request=call_context.request,
                target_glue_policy=child_policy,
                target_glue_updates=data.get('updates', {}),
            )

        # Every submitted row's record is loaded in one query, keyed by the
        # string form of its pk because a signed pk is a JSON value.
        instances: dict[str, Model] = {}
        target_pks = [
            context.target_glue_policy.identity['target_pk']
            for context in child_contexts.values()
            if context.target_glue_policy.identity.get('target_pk') is not None
        ]
        if target_pks and issubclass(self.form_class, ModelForm):
            model = self.form_class._meta.model
            many_to_many = [
                field.name
                for field in model._meta.many_to_many
                if field.name in self.form_class.base_fields
            ]
            loaded = model._default_manager.prefetch_related(*many_to_many).in_bulk(target_pks)
            instances = {str(pk): instance for pk, instance in loaded.items()}

        for key, child_context in child_contexts.items():
            child_policy = child_context.target_glue_policy
            form = FormGlue._reconstruct_from_policy(
                child_policy,
                instance=instances.get(str(child_policy.identity.get('target_pk'))),
            )
            form._authorize_reconstruction(child_context)
            form._hydrate(child_policy, child_context.target_glue_updates)
            self._forms.append((key, form))

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormSetGlue:
        # Needed if the target is a Glue.FormSet subclass
        formset_class = get_attr_from_path_string(policy.identity['formset_class_path'])

        form_class = (
            getattr(formset_class, 'form_class', None)
            or get_attr_from_path_string(policy.identity['form_class_path'])
        )

        formset = formset_class(
            form_class,
            name=policy.name,
            access=policy.access,
            min_num=policy.identity['min_num'],
            max_num=policy.identity['max_num'],
            can_delete=policy.identity['can_delete'],
            new_row_defaults=policy.identity.get('new_row_defaults'),
            _reconstructed=True,
        )

        formset._live_children = dict(policy.children)
        formset._removed_pks = list(policy.state_snapshot.get('removed_pks', []))
        formset._row_bindings = policy.state_snapshot.get('row_bindings')

        return formset

from __future__ import annotations

from typing import Any, Mapping, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueFormSetMaxNumExceededError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.collection import BaseCollectionGlue
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django import forms

    from django_glue.glue.base import BaseGlue


class FormSetGlue(BaseCollectionGlue):
    """A keyed collection of ``FormGlue`` children sharing a single form class.

    Replaces the legacy ``BaseFormSet`` substrate (ADR 012). The formset owns
    the order/membership (the keys) and the formset-level concerns; per-form
    work is delegated to the ``FormGlue`` children. The collection starts
    empty -- ``min_num`` / ``max_num`` are validation floors/ceilings, not a
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
        self._forms: list[tuple[str, FormGlue]] = []
        self._live_children: dict[str, str] = {}
        self._reconstructed = _reconstructed

    def get_identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.form_class.__module__}.{self.form_class.__qualname__}',
            'formset_class_path': f'{self.__class__.__module__}.{self.__class__.__qualname__}',
            'min_num': self.min_num,
            'max_num': self.max_num,
            'can_delete': self.can_delete,
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

    def clean(self, form_list: list[forms.BaseForm]) -> list[str]:  # noqa: ARG002
        """Cross-form validation hook. Override to add formset-level errors.

        Receives the plain, already-validated Django ``Form``s (never
        ``FormGlue``s) so application code stays Django-idiomatic.
        """
        return []

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def append(self, key: str, initial: dict[str, Any] | None = None) -> FormGlue:
        if key in self._live_children or any(existing == key for existing, _ in self._forms):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Formset row key is already in use.',
            )
        count = len(set(self._live_children) | {row_key for row_key, _ in self._forms})
        if self.max_num is not None and count >= self.max_num:
            raise GlueFormSetMaxNumExceededError(count, self.max_num)
        form = self.form_class(initial=initial or {})
        form_glue = self._build_form_glue(form, key)
        self._forms.append((key, form_glue))
        return form_glue

    @DeclaredAttribute(required_access=GlueAccess.CHANGE)
    def pop(self, key: str) -> None:
        if not self.can_delete:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='This formset does not allow row removal.',
            )
        if key in self._live_children:
            del self._live_children[key]
            self._forms = [(row_key, form) for row_key, form in self._forms if row_key != key]
            return
        for index, (existing, _) in enumerate(self._forms):
            if existing == key:
                self._forms.pop(index)
                return
        raise GlueRequestError(
            code=GlueRequestErrorCode.INVALID_KWARGS,
            message='Formset row key is not live.',
        )

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
        results = [form.save() for _, form in self._forms]
        return {'valid': all(result['valid'] for result in results)}

    def _build_form_glue(self, form: forms.BaseForm, key: str) -> FormGlue:
        return FormGlue(form, name=f'{self.name}.{key}', access=self.access)

    def _load_client_state(self, state: dict[str, Any]) -> None:
        if 'forms' not in state:
            return
        self._forms = []
        for key, form_state in (state.get('forms') or {}).items():
            form_glue = self._build_form_glue(self.form_class(initial={}), key)
            form_glue._load_client_state(form_state)
            self._forms.append((key, form_glue))

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        kwargs = dict(call_context.target_attribute_call_kwargs)
        submitted = kwargs.pop('__forms', None)
        if submitted is not None:
            self._hydrate_submitted_forms(call_context, submitted)
        elif self._live_children and call_context.target_attribute_name not in {'append', 'pop'}:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Every live formset row must be submitted with its signed form token.',
            )

        entry, introduced = super().process_attribute_call(
            call_context.model_copy(update={'target_attribute_call_kwargs': kwargs}),
        )
        if submitted is not None:
            introduced.extend(form.entry.model_dump() for _, form in self._forms)
        if call_context.target_attribute_name == 'validate':
            entry['result']['form_list'] = [form.address for _, form in self._forms]
        return entry, introduced

    def _hydrate_submitted_forms(
        self,
        call_context: AttributeCallRequestContext,
        submitted: Any,
    ) -> None:
        if not isinstance(submitted, dict) or set(submitted) != set(self._live_children):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message='Submitted formset rows must match signed membership.',
            )
        for key in self._live_children:
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
            ):
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='Submitted form token does not belong to this formset row.',
                )
            updates = data.get('updates', {})
            child_context = AttributeCallRequestContext.model_construct(
                request=call_context.request,
                target_glue_policy=child_policy,
                target_glue_updates=updates,
            )
            form = FormGlue.from_attribute_call_resolver_context(child_context)
            form._hydrate(child_policy, updates)
            self._forms.append((key, form))

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormSetGlue:
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
            _reconstructed=True,
        )
        formset._live_children = dict(policy.children)
        return formset

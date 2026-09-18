from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.access import GlueAccess
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.collection import BaseCollectionGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django import forms

    from django_glue.glue.base import BaseGlue
    from django_glue.glue.policy import GluePolicy


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
        loading_strategy: LoadingStrategy = LoadingStrategy.EAGER,
        _reconstructed: bool = False,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        cls = self.__class__
        self.form_class = form_class if form_class is not None else cls.form_class
        if self.form_class is None:
            msg = f"FormSetGlue '{name}' requires a form_class."
            raise ValueError(msg)
        self.min_num = cls.min_num if min_num is None else min_num
        self.max_num = cls.max_num if max_num is None else max_num
        self.can_delete = cls.can_delete if can_delete is None else can_delete
        self._forms: list[tuple[str, FormGlue]] = []
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

    def get_state(self) -> dict[str, Any]:
        return {'forms': {key: form.state for key, form in self._forms}}

    def get_metadata(self) -> dict[str, Any]:
        return {'attributes': {}}

    def clean(self, form_list: list[forms.BaseForm]) -> list[str]:  # noqa: ARG002
        """Cross-form validation hook. Override to add formset-level errors.

        Receives the plain, already-validated Django ``Form``s (never
        ``FormGlue``s) so application code stays Django-idiomatic.
        """
        return []

    @DeclaredAttribute(
        required_access=GlueAccess.CHANGE,
        takes_client_state=False,
        updates_client_state=False,
    )
    def append(self, key: str, initial: dict[str, Any] | None = None) -> FormGlue:
        form = self.form_class(initial=initial or {})
        form_glue = self._build_form_glue(form, key)
        self._forms.append((key, form_glue))
        return form_glue

    @DeclaredAttribute(
        required_access=GlueAccess.CHANGE,
        updates_client_state=False,
    )
    def validate(self) -> dict[str, Any]:
        form_glues = [form for _, form in self._forms]
        per_form = [form.validate() for form in form_glues]
        bound_forms = [form._bound_form for form in form_glues]
        non_form_errors = self.clean(bound_forms)
        valid = all(result['valid'] for result in per_form) and not non_form_errors
        return {
            'valid': valid,
            'form_list': form_glues,
            'non_form_errors': non_form_errors,
        }

    @DeclaredAttribute(
        required_access=GlueAccess.CHANGE,
        updates_client_state=False,
    )
    def save(self) -> dict[str, Any]:
        results = [form.save() for _, form in self._forms]
        return {'valid': all(result['valid'] for result in results)}

    def _build_form_glue(self, form: forms.BaseForm, key: str) -> FormGlue:
        return FormGlue(
            form,
            name=f'{self.name}.{key}',
            access=self.access,
            loading_strategy=LoadingStrategy.EAGER,
        )

    def _load_client_state(self, state: dict[str, Any]) -> None:
        self._forms = []
        for key, form_state in (state.get('forms') or {}).items():
            form_glue = self._build_form_glue(self.form_class(initial={}), key)
            form_glue._load_client_state(form_state)
            self._forms.append((key, form_glue))

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormSetGlue:
        formset_class = get_attr_from_path_string(policy.identity['formset_class_path'])
        form_class = (
            getattr(formset_class, 'form_class', None)
            or get_attr_from_path_string(policy.identity['form_class_path'])
        )
        return formset_class(
            form_class,
            name=policy.name,
            access=policy.access,
            min_num=policy.identity['min_num'],
            max_num=policy.identity['max_num'],
            can_delete=policy.identity['can_delete'],
            _reconstructed=True,
        )

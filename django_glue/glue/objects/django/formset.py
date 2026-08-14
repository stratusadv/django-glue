from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from django import forms
from django.forms import formset_factory

from django_glue.access import GlueAccess
from django_glue.glue.attributes import BaseGlueAttribute, DeclaredAttribute, GlueObjectAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.utils import get_attr_from_path_string

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class FormSetGlue(BaseGlue):
    namespace = 'formSet'

    def __init__(
        self,
        formset: forms.BaseFormSet,
        *,
        name: str,
        access: GlueAccess = GlueAccess.CHANGE,
        loading_strategy: LoadingStrategy = LoadingStrategy.EAGER,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.formset = formset

    def get_identity(self) -> dict[str, Any]:
        return {
            'form_class_path': f'{self.formset.form.__module__}.{self.formset.form.__name__}',
            'formset_class_path': self._formset_base_class_path(),
            'prefix': self.formset.prefix,
            'min_num': self.formset.min_num,
            'max_num': self.formset.max_num,
            'absolute_max': self.formset.absolute_max,
            'validate_min': self.formset.validate_min,
            'validate_max': self.formset.validate_max,
            'can_delete': self.formset.can_delete,
        }

    def get_attribute_providers(self) -> dict[str, Any]:
        return {'formset': self.formset}

    # Nested forms are declared under 'form_list.{index}' rather than
    # 'forms.{index}': the frontend GlueFormSetProxy exposes a public
    # `forms` getter for its current list of form proxies, and
    # BaseGlueProxy's generic nested-attribute resolution walks a
    # same-named plain property on the proxy instance to attach each
    # nested form -- naming the wire attribute 'forms' would collide with
    # that getter and throw during proxy construction (before the
    # subclass's own constructor body has run).
    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        attributes = dict(super().attributes)
        attributes.update({
            f'form_list.{index}': GlueObjectAttribute(
                owner=self,
                name=f'form_list.{index}',
                access=self.access,
                glue_object=self._build_form_glue(form, str(index)),
            )
            for index, form in enumerate(self.formset.forms)
        })
        return attributes

    @DeclaredAttribute(
        access=GlueAccess.CHANGE,
        takes_client_state=False,
        updates_client_state=False,
    )
    def append(self, key: str, initial: dict[str, Any] | None = None) -> FormGlue:
        form = self.formset.form(initial=initial or {}, prefix=f'{self.formset.prefix}-{key}')
        return self._build_form_glue(form, key)

    @DeclaredAttribute(
        access=GlueAccess.CHANGE,
        updates_client_state=False,
    )
    def validate(self) -> dict[str, Any]:
        valid = self.formset.is_valid()
        return {
            'valid': valid,
            'form_list': [
                self._build_form_glue(form, str(index))
                for index, form in enumerate(self.formset.forms)
            ],
            'non_form_errors': list(self.formset.non_form_errors()),
        }

    def _load_client_state(self, state: dict[str, Any]) -> None:
        self.formset = self._bind_formset(state.get('form_list', []))

    def _formset_base_class_path(self) -> str:
        base_class = self.formset.__class__.__mro__[1]
        return f'{base_class.__module__}.{base_class.__name__}'

    def _bind_formset(self, forms_state: list[dict[str, Any]]) -> forms.BaseFormSet:
        prefix = self.formset.prefix
        data: dict[str, Any] = {
            f'{prefix}-TOTAL_FORMS': len(forms_state),
            f'{prefix}-INITIAL_FORMS': 0,
            f'{prefix}-MIN_NUM_FORMS': self.formset.min_num,
            f'{prefix}-MAX_NUM_FORMS': self.formset.max_num,
        }
        for index, form_state in enumerate(forms_state):
            for field_name, field_state in form_state.items():
                value = field_state.get('value') if isinstance(field_state, dict) else field_state
                data[f'{prefix}-{index}-{field_name}'] = value
        return self.formset.__class__(data=data, prefix=prefix)

    def _build_form_glue(self, form: forms.BaseForm, key: str) -> FormGlue:
        return FormGlue(
            form,
            name=f'{self.name}.form_list.{key}',
            access=self.access,
            loading_strategy=LoadingStrategy.EAGER,
        )

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> FormSetGlue:
        form_class = get_attr_from_path_string(policy.identity['form_class_path'])
        formset_base_class = get_attr_from_path_string(policy.identity['formset_class_path'])
        formset_class = formset_factory(
            form_class,
            formset=formset_base_class,
            extra=0,
            min_num=policy.identity['min_num'],
            max_num=policy.identity['max_num'],
            absolute_max=policy.identity['absolute_max'],
            validate_min=policy.identity['validate_min'],
            validate_max=policy.identity['validate_max'],
            can_delete=policy.identity['can_delete'],
        )
        return cls(
            formset_class(prefix=policy.identity['prefix']),
            name=policy.name,
            access=policy.access,
        )

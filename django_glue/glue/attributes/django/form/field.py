from __future__ import annotations

from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.django.field import BaseDjangoFieldGlueAttribute

if TYPE_CHECKING:
    from django import forms

    from django_glue.access import GlueAccess
    from django_glue.glue.base import BaseGlue


class FormFieldAttribute(BaseDjangoFieldGlueAttribute):
    """GlueAttribute for a Django form field."""

    def __init__(
        self,
        *,
        owner: BaseGlue,
        name: str,
        field: forms.Field,
        form: forms.BaseForm,
        required_access: GlueAccess,
    ) -> None:
        super().__init__(owner=owner, name=name, field=field, required_access=required_access)
        self.form = form

    def add_choice_metadata(self, metadata: dict[str, Any]) -> None:
        if hasattr(self.field, 'queryset'):
            metadata['choices'] = []
            metadata['pk_field'] = self.field.queryset.model._meta.pk.name
            metadata['choice_model_path'] = (
                f'{self.field.queryset.model.__module__}.{self.field.queryset.model.__name__}'
            )
            metadata['choices_cache_key'] = (
                f'{self.form.__class__.__module__}.{self.form.__class__.__name__}.'
                f'{self.name}.{self.field.queryset.model._meta.label_lower}'
            )
            return
        super().add_choice_metadata(metadata)

    def add_extra_metadata(self, metadata: dict[str, Any]) -> None:
        metadata['disabled'] = self.field.disabled
        metadata['widget'] = self.field.widget.__class__.__name__

    def get(self) -> Any:
        if self.form.is_bound:
            return self.form.data.get(self.name)

        # Unlike bound form.data (already plain submitted values), an unbound
        # ModelForm's initial can hold raw model instances/querysets for
        # Model(Multiple)ChoiceField (e.g. instance=obj populates initial from
        # model_to_dict, which passes M2M/FK values through as model
        # instances, not PKs). prepare_value() is what Django's own rendering
        # path uses to reduce those to serializable values -- without it the
        # client receives full nested objects instead of PKs, which then fail
        # Model(Multiple)ChoiceField.clean() as "Enter a list of values."
        # (or an invalid choice) on save. Mirrors FormGlue._prepared_initial.
        #
        # get_initial_for_field() (not form.initial.get(self.name) alone) is
        # what actually matches Django's own BoundField.value(): it falls
        # back to field.initial when the form-level initial dict has nothing
        # for this field, same as a classically-rendered <input> would. Without
        # that fallback, a field.initial set post-construction (e.g. in a
        # ModelForm.__init__ override for a non-model field) is silently
        # ignored here even though it renders fine in a normal Django form.
        return self.field.prepare_value(
            self.form.get_initial_for_field(self.field, self.name)
        )

    @property
    def state(self) -> dict[str, Any] | None:
        return {
            'value': self.get(),
            'errors': self.owner._field_errors.get(self.name, []),
        }

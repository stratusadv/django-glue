from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.forms import ModelMultipleChoiceField

from django_glue.glue.attributes.django.field import BaseDjangoFieldGlueAttribute
from django_glue.glue.options.django import GlueRelatedModelChoices

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
            related_choices = GlueRelatedModelChoices(
                self.field.queryset,
                value_field_name=getattr(self.field, 'to_field_name', None),
            )
            metadata['choices'] = []
            metadata['pk_field'] = self.field.queryset.model._meta.pk.name
            metadata['choice_model_path'] = (
                f'{self.field.queryset.model.__module__}.{self.field.queryset.model.__name__}'
            )
            metadata['choices_cache_key'] = (
                f'{self.form.__class__.__module__}.{self.form.__class__.__name__}.'
                f'{self.name}.{self.field.queryset.model._meta.label_lower}.'
                f'{related_choices.fingerprint()}'
            )
            metadata['choices_searchable'] = related_choices.is_searchable
            if related_choices.is_searchable:
                self._add_selected_choice_metadata(
                    metadata=metadata,
                    related_choices=related_choices,
                )
            return
        super().add_choice_metadata(metadata)

    def _add_selected_choice_metadata(
        self,
        metadata: dict[str, Any],
        related_choices: GlueRelatedModelChoices,
    ) -> None:
        """Seed the currently selected choice(s) before a searchable field is queried.

        Searchable sources deliberately return no unfiltered result set, so a
        single-value field seeds ``selected_choice`` and a multiple-value field
        seeds one ``selected_choices`` entry per selection. This lets the browser
        render the form's current value without weakening that rule or issuing a
        search request.
        """
        current_value = self.field.prepare_value(
            self.form.get_initial_for_field(self.field, self.name)
        )
        if current_value in (None, ''):
            return

        is_multiple = isinstance(self.field, ModelMultipleChoiceField)
        values = list(current_value) if is_multiple else [current_value]
        selected_choices = related_choices.serialize_selected_values(values)
        if not selected_choices:
            return

        if is_multiple:
            metadata['selected_choices'] = selected_choices
        else:
            metadata['selected_choice'] = selected_choices[0]

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

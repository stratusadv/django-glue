from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.forms import ModelMultipleChoiceField

from django_glue.glue.attributes.adapter import GlueAttributeAdapter
from django_glue.glue.options.django import GlueRelatedModelChoices

if TYPE_CHECKING:
    from django import forms
    from django.db import models

    from django_glue.glue.objects.django.form.object import FormGlue
    from django_glue.glue.objects.django.model.object import ModelGlue


def _field_schema(field: Any, *, editable: bool) -> dict[str, Any]:
    label = str(
        getattr(field, 'label', None)
        or getattr(field, 'verbose_name', '')
        or ''
    )
    required = (
        bool(field.required)
        if hasattr(field, 'required')
        else not getattr(field, 'blank', False)
        and not getattr(field, 'null', False)
    )
    schema = {
        'namespace': 'field',
        'type': field.__class__.__name__,
        'label': label.capitalize() if label else '',
        'required': required,
        'help_text': str(getattr(field, 'help_text', '') or ''),
        'editable': editable,
        'disabled': not editable,
    }
    if getattr(field, 'max_length', None):
        schema['max_length'] = field.max_length
    if getattr(field, 'min_length', None):
        schema['min_length'] = field.min_length
    if getattr(field, 'choices', None):
        schema['choices'] = [
            {'value': str(value), 'label': str(choice_label)}
            for value, choice_label in field.choices
        ]
    return schema


@dataclass(frozen=True, slots=True)
class FormFieldAdapter(GlueAttributeAdapter):
    owner: FormGlue
    name: str
    field: forms.Field

    def schema(self) -> dict[str, Any]:
        schema = _field_schema(
            self.field,
            editable=self.name in self.owner.editable,
        )
        schema['widget'] = self.field.widget.__class__.__name__
        if not hasattr(self.field, 'queryset'):
            return schema

        related_choices = GlueRelatedModelChoices(
            self.field.queryset,
            value_field_name=getattr(self.field, 'to_field_name', None),
        )
        schema.update({
            'choices': [],
            'pk_field': self.field.queryset.model._meta.pk.name,
            'choice_model_path': (
                f'{self.field.queryset.model.__module__}.'
                f'{self.field.queryset.model.__name__}'
            ),
            'choices_cache_key': (
                f'{self.owner.form.__class__.__module__}.'
                f'{self.owner.form.__class__.__name__}.{self.name}.'
                f'{self.field.queryset.model._meta.label_lower}.'
                f'{related_choices.fingerprint()}'
            ),
            'choices_searchable': related_choices.is_searchable,
        })
        if not related_choices.is_searchable:
            return schema

        current_value = self.field.prepare_value(
            self.owner.form.get_initial_for_field(self.field, self.name)
        )
        if current_value in (None, ''):
            return schema
        is_multiple = isinstance(self.field, ModelMultipleChoiceField)
        values = list(current_value) if is_multiple else [current_value]
        selected_choices = related_choices.serialize_selected_values(values)
        if is_multiple:
            schema['selected_choices'] = selected_choices
        elif selected_choices:
            schema['selected_choice'] = selected_choices[0]
        return schema

    def unsigned_data(self) -> dict[str, Any]:
        return {'errors': self.owner._field_errors.get(self.name, [])}


@dataclass(frozen=True, slots=True)
class ModelFieldAdapter(GlueAttributeAdapter):
    owner: ModelGlue
    name: str
    field: models.Field

    def schema(self) -> dict[str, Any]:
        schema = _field_schema(
            self.field,
            editable=self.name in self.owner.editable,
        )
        related_model = getattr(self.field, 'related_model', None)
        if (
            not getattr(self.field, 'is_relation', False)
            or related_model is None
            or not getattr(self.field, 'concrete', False)
        ):
            return schema

        field_name = getattr(self.field, 'name', self.name)
        choice_queryset = self.owner._choice_queryset_for_field(field_name)
        related_choices = GlueRelatedModelChoices(
            choice_queryset,
            value_field_name=self.owner._choice_value_field_name_for_field(field_name),
        )
        selected_value = self.owner._get_model_attribute_value(self.name)
        selected_values = (
            selected_value
            if getattr(self.field, 'many_to_many', False)
            else [selected_value]
        )
        selected_choices = (
            related_choices.serialize_selected_values(selected_values)
            if related_choices.is_searchable
            else []
        )
        schema.update({
            'choices': [],
            'pk_field': related_model._meta.pk.name,
            'choice_model_path': (
                f'{related_model.__module__}.{related_model.__name__}'
            ),
            'related_model': (
                f'{related_model.__module__}.{related_model.__name__}'
            ),
            'choices_cache_key': (
                f'{self.owner.instance.__class__._meta.label_lower}.{self.name}.'
                f'{related_model._meta.label_lower}.{related_choices.fingerprint()}'
            ),
            'choices_searchable': related_choices.is_searchable,
        })
        if getattr(self.field, 'many_to_many', False):
            schema['selected_choices'] = selected_choices
        elif selected_choices:
            schema['selected_choice'] = selected_choices[0]
        return schema

    def unsigned_data(self) -> dict[str, Any]:
        return {'errors': self.owner._field_errors.get(self.name, [])}

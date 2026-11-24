from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from django_glue.glue.children import GlueChildType, glue_child_type_registry
from django_glue.glue.objects.django.form.object import FormGlue

if TYPE_CHECKING:
    from django_glue.access import GlueAccess


class FormChildType(GlueChildType):
    """A Django form returned by a child's method: a FormGlue island, read as the form (ADR 050)."""

    value_type = forms.BaseForm
    glue_class = FormGlue
    options = frozenset({'editable'})

    @classmethod
    def wrap(cls, value: forms.BaseForm, *, name: str, access: GlueAccess, **options: Any) -> FormGlue:
        return FormGlue(value, name=name, access=access, **options)

    @classmethod
    def read(cls, glue_object: FormGlue) -> forms.BaseForm:
        return glue_object.as_form()


glue_child_type_registry.register(FormChildType)

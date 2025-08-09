from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.glue.form.fields import models


class FieldsForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Fields
        fields: ClassVar = []

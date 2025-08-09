from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.glue.form import models


class FormForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Form
        fields: ClassVar = []

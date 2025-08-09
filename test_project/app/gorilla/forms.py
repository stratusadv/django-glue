from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.app.gorilla import models


class GorillaForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Gorilla
        fields: ClassVar = []

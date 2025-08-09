from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.app.gorilla.capability import models


class CapabilityForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Capability
        fields: ClassVar = []

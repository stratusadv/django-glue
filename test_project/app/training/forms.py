from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.app.training import models


class TrainingForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Training
        fields: ClassVar = []

from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.app.fight.round import models


class RoundForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Round
        fields: ClassVar = []

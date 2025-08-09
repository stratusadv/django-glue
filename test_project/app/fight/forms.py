from __future__ import annotations

from typing_extensions import ClassVar

from django import forms

from test_project.app.fight import models


class FightForm(forms.ModelForm):
    field = forms.JSONField(required=False)

    class Meta:
        model = models.Fight
        fields: ClassVar = []

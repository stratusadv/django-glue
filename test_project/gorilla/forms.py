from django import forms

from test_project.gorilla.models import Gorilla


class GorillaForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = ['name', 'description', 'age', 'weight', 'height', 'fight_style', 'rank_points']

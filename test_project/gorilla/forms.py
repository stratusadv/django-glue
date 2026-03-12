from django import forms

from test_project.gorilla.models import Gorilla, Skill


class GorillaForm(forms.ModelForm):
    class Meta:
        model = Gorilla
        fields = [
            'name', 'description', 'age', 'weight', 'height', 'rank_points',
            'profile_photo', 'skills'
        ]


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'description', 'difficulty', 'level']

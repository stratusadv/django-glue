from django import forms

from test_project.gorilla.models import Gorilla, Skill


class GorillaForm(forms.ModelForm):
    def clean_rank_points(self):
        rank_points = self.cleaned_data['rank_points']

        if rank_points > 0:
            raise forms.ValidationError("How can this gorilla have rank points, they are new!")

        return rank_points

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

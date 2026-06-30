from django import forms
from django.core.handlers.wsgi import WSGIRequest

from django_glue.form.form import GlueModelForm
from django_glue.response import GlueJsonResponse
from test_project.gorilla.models import Gorilla, Skill


class GorillaForm(forms.ModelForm):
    def clean_rank_points(self):
        rank_points = self.cleaned_data['rank_points']

        if rank_points > 0:
            raise forms.ValidationError('How can this gorilla have rank points, they are new!')

        return rank_points

    class Meta:
        model = Gorilla
        fields = [
            'name',
            'description',
            'age',
            'weight',
            'height',
            'rank_points',
            'profile_photo',
            'skills',
        ]


class GorillaGlueModelForm(GlueModelForm):
    def process(self, request: WSGIRequest, payload: dict) -> GlueJsonResponse:
        return self.GlueJsonResponse({'hello': 'world'})

    class Meta:
        model = Gorilla
        exclude = ['pk']


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'description', 'difficulty', 'level']

from django import forms

from test_project.lab.models import Specimen


class SpecimenForm(forms.ModelForm):
    class Meta:
        model = Specimen
        fields = ['name', 'species', 'weight', 'catalogue_number', 'collector', 'habitats']

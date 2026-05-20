from django import forms
from test_project.gorilla.models import Gorilla


class ContactForm(forms.Form):
    """Simple contact form for testing non-ModelForm functionality."""

    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    priority = forms.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], required=True
    )


class TestModelForm(forms.ModelForm):
    """ModelForm for Gorilla model, used in form proxy tests."""

    class Meta:
        model = Gorilla
        fields = ['name', 'description', 'age', 'weight', 'height']

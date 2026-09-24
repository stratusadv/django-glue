from django import forms
from django_glue import Glue
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla


class ContactForm(forms.Form):
    """Simple contact form for testing non-ModelForm functionality."""

    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    priority = forms.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], required=True
    )


class SaveValidatingForm(forms.Form):
    """Plain form whose save callable validates itself via is_valid(), the
    shape consumer save_model_obj() methods take.
    """

    title = forms.CharField()
    hours = forms.FloatField()

    @Glue.attr
    def save_entry(self) -> dict:
        if self.is_valid():
            return {'success': True}
        return {'success': False, 'errors': self.errors}


class ContactFormSet(Glue.FormSet):
    form_class = ContactForm
    min_num = 1
    max_num = 5
    can_delete = True

    @Glue.attr(required_access=Glue.Access.CHANGE)
    def submit(self) -> dict:
        validation = self.validate()
        return {
            'valid': validation['valid'],
            'names': [form.bound_form.cleaned_data['name'] for form in validation['form_list']]
            if validation['valid'] else [],
        }


class TestModelForm(forms.ModelForm):
    """ModelForm for Gorilla model, used in form proxy tests."""

    class Meta:
        model = Gorilla
        fields = ['name', 'description', 'age', 'weight', 'height']


class FightForm(forms.ModelForm):
    """ModelForm for Fight model (has required FK fields), used in form proxy tests."""

    class Meta:
        model = Fight
        fields = ['name', 'red_corner', 'blue_corner']

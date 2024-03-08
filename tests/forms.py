from django import forms

from tests.fields import ItemRequestField

class ComplexFormIntegrationForm(forms.Form):
    location = forms.ChoiceField()
    item_request = ItemRequestField()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:
            raise forms.ValidationError('Passwords do not match')

        return cleaned_data

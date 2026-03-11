from django import forms
from django.core.exceptions import ValidationError

from test_project.fight.models import Fight


class FightForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        red_corner = cleaned_data.get('red_corner')
        blue_corner = cleaned_data.get('blue_corner')

        if red_corner and blue_corner and red_corner == blue_corner:
            raise ValidationError("Red and blue corners cannot be the same gorilla.")

        return cleaned_data

    class Meta:
        model = Fight
        fields = [
            'name', 'description', 'red_corner', 'blue_corner', 'status',
            'location', 'weather_conditions', 'spectator_count', 'terrain_type'
        ]


class ContactPromoterForm(forms.Form):
    """Regular (non-Model) form for contacting the fight promoter."""
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    subject = forms.ChoiceField(choices=[
        ('sponsorship', 'Sponsorship Inquiry'),
        ('fighter', 'Fighter Registration'),
        ('media', 'Media Credentials'),
        ('tickets', 'Ticket Information'),
        ('other', 'Other'),
    ])
    message = forms.CharField(widget=forms.Textarea, required=True, min_length=10)

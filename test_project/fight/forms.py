from django import forms

from test_project.fight.models import Fight


class FightForm(forms.ModelForm):
    class Meta:
        model = Fight
        fields = [
            'name', 'description', 'red_corner', 'blue_corner',
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

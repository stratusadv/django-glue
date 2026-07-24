from django import forms
from django.core.handlers.wsgi import WSGIRequest

from django_glue import Glue
from django_glue.response import GlueResponse
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
            'fighting_stats',
        ]


class GorillaGlueModelForm(forms.ModelForm):
    """
    Multi-step progressive form for creating a gorilla fighter.

    Demonstrates how GlueForm's process() method can handle
    complex, state-based form workflows with step validation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional for step-by-step validation in process()
        for field in self.fields.values():
            field.required = False

    @Glue.attribute(access=Glue.Access.DELETE)
    def process(self, request: WSGIRequest, step: int = 1, **kwargs) -> GlueResponse:
        """
        Handle progressive form steps.

        The frontend calls this method for each step, passing:
        - step: Current step number (1, 2, or 3)
        - The form field values are available via self.data

        Step 1: Basic info (name, age)
        Step 2: Physical attributes (weight, height)
        Step 3: Final details (description) - saves the model
        """
        Message = GlueResponse.Message
        self.full_clean()

        if step == 1:
            # Validate basic info fields
            if not self.data.get('name'):
                self.add_error('name', 'Name is required.')
            if not self.data.get('age'):
                self.add_error('age', 'Age is required.')
            elif int(self.data.get('age', 0)) < 1:
                self.add_error('age', 'Age must be at least 1.')

            if self.errors:
                return GlueResponse(
                    result={'step': step},
                    messages=[Message(Message.Level.ERROR, 'Please fix the errors above.')],
                )

            return GlueResponse(
                result={'step': step, 'next_step': 2},
                messages=[Message(Message.Level.SUCCESS, 'Basic info validated!')],
            )

        elif step == 2:
            # Validate physical attributes
            if not self.data.get('weight'):
                self.add_error('weight', 'Weight is required.')
            elif float(self.data.get('weight', 0)) < 50:
                self.add_error('weight', 'Weight must be at least 50 kg.')

            if not self.data.get('height'):
                self.add_error('height', 'Height is required.')
            elif float(self.data.get('height', 0)) < 1.0:
                self.add_error('height', 'Height must be at least 1.0 m.')

            if self.errors:
                return GlueResponse(
                    result={'step': step},
                    messages=[Message(Message.Level.ERROR, 'Please fix the errors above.')],
                )

            return GlueResponse(
                result={'step': step, 'next_step': 3},
                messages=[Message(Message.Level.SUCCESS, 'Physical attributes validated!')],
            )

        elif step == 3:
            # Final step - validate and save the model
            if self.is_valid():
                gorilla = self.save()
                return GlueResponse(
                    result={'step': step, 'gorilla_id': gorilla.pk},
                    messages=[Message(Message.Level.SUCCESS, f'Fighter "{gorilla.name}" created!')],
                )
            else:
                return GlueResponse(
                    result={'step': step},
                    messages=[Message(Message.Level.ERROR, 'Please fix the validation errors.')],
                )

        return GlueResponse(
            messages=[Message(Message.Level.ERROR, f'Invalid step: {step}')],
        )

    class Meta:
        model = Gorilla
        fields = [
            'name',
            'description',
            'age',
            'weight',
            'height',
        ]


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'description', 'difficulty', 'level']

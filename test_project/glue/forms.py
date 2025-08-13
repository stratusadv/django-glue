from __future__ import annotations

# Note: We're using Django's built-in session system instead of a custom model
# The SessionDataForm below is commented out as it's no longer needed

# from typing_extensions import ClassVar
# from django import forms
# from test_project.glue.models import SessionData
#
#
# class SessionDataForm(forms.ModelForm):
#     data = forms.JSONField(required=False)
#
#     class Meta:
#         model = SessionData
#         fields: ClassVar = ['session_id', 'data']

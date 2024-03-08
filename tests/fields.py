import json

from django import forms

from tests import widgets
from tests.validators import validate_item_request_form_field


class ItemRequestField(forms.CharField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = widgets.ItemRequestWidget()
        self.validators.append(validate_item_request_form_field)

    def clean(self, value):
        super().clean(value)
        return json.loads(value)
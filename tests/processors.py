import json
from dataclasses import dataclass
from tests import forms


def get_complex_form_processor(form_data):
    if form_data.get('location') == 'NYC':
        return forms.NewYorkForm(data=form_data)

    elif form_data.get('location') == 'CHI':
        return forms.ChicagoForm(data=form_data)


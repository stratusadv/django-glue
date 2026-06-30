from abc import abstractmethod, ABC
from typing import Any

from django.core.handlers.wsgi import WSGIRequest
from django.forms import Form
from django.forms.models import ModelForm
from django.http import JsonResponse

from django_glue.form.response import JsonFormResponse
from test_project.gorilla.models import Gorilla


class _BaseJsonForm(ABC):
    @abstractmethod
    def process(self, request: WSGIRequest, payload: dict) -> JsonFormResponse:
        raise NotImplementedError


class BaseJsonForm(Form, _BaseJsonForm, ABC):
    pass


class BaseJsonModelForm(ModelForm, _BaseJsonForm, ABC):
    pass

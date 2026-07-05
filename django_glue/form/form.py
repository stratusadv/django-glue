from abc import ABCMeta, abstractmethod, ABC

from django.core.handlers.wsgi import WSGIRequest
from django.forms import Form
from django.forms.models import ModelForm, ModelFormMetaclass
from django.forms.forms import DeclarativeFieldsMetaclass

from django_glue.access.access import GlueAccess
from django_glue.proxies.decorators import action
from django_glue.response import ActionResult


class _FormDeclarativeFieldsMetaclassABCMixin(DeclarativeFieldsMetaclass, ABCMeta):
    pass


class _ModelFormMetaclassABCMixin(ModelFormMetaclass, ABCMeta):
    pass


class _BaseGlueForm(ABC):
    GlueJsonResponse = ActionResult

    @abstractmethod
    @action(access=GlueAccess.DELETE)
    def process(self, request: WSGIRequest, payload: dict) -> GlueJsonResponse:
        raise NotImplementedError

class GlueForm(_BaseGlueForm, Form, metaclass=_FormDeclarativeFieldsMetaclassABCMixin):
    pass


class GlueModelForm(_BaseGlueForm, ModelForm, metaclass=_ModelFormMetaclassABCMixin):
    pass

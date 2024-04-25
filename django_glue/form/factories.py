from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.db.models import Model, Field
from django_glue.form import fields


@dataclass
class GlueFieldFactory(ABC):
    model_object: Model
    model_field: Field

    @abstractmethod
    def factory_method(self):
        pass


@dataclass
class GlueCharFieldFactory(GlueFieldFactory):

    def factory_method(self):
        return fields.CharField()

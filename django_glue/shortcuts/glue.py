from typing import Sequence

from django.db.models import Model, QuerySet
from django.forms import BaseForm, ModelForm
from django.http import HttpRequest

from django_glue.access import GlueAccess
from django_glue.glue.base import BaseGlue
from django_glue.glue.context import GlueContextManager
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.objects.django.template import TemplateGlue
from django_glue.glue.function import FunctionGlue
from django_glue.glue.attributes import Attribute


class Glue:
    Access = GlueAccess
    Attribute = Attribute

    @staticmethod
    def object(
        request: HttpRequest,
        glue: BaseGlue,
    ) -> None:
        GlueContextManager(request).add_glue(glue)

    @staticmethod
    def model(
        request: HttpRequest,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
    ) -> None:
        Glue.object(
            request=request,
            glue=ModelGlue(
                instance=target,
                request=request,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
                form_class=form_class,
            ),
        )

    @staticmethod
    def queryset(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
    ) -> None:
        Glue.object(
            request=request,
            glue=QuerySetGlue(
                queryset=target,
                request=request,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
            ),
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.VIEW,
    ) -> None:
        Glue.object(
            request=request,
            glue=FormGlue( #TODO: remove DJANGO
                form=target,
                request=request,
                name=unique_name,
                access=access,
            ),
        )

    @staticmethod
    def template(
        request: HttpRequest,
        unique_name: str,
        target: str,
        initial_context_data: dict | None = None,
    ) -> None:
        Glue.object(
            request=request,
            glue=TemplateGlue(
                target,
                request=request,
                name=unique_name,
                access=GlueAccess.VIEW,
                initial_context_data=initial_context_data,
            ),
        )

    @staticmethod
    def function(
        request: HttpRequest,
        unique_name: str,
        target: str,
    ) -> None:
        Glue.object(
            request=request,
            glue=FunctionGlue(
                target,
                request=request,
                name=unique_name,
                access=GlueAccess.VIEW,
            ),
        )

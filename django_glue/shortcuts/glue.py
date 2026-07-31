from typing import Mapping, Sequence

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
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.response import GlueRedirectResponse, GlueResponse


class Glue:
    Access = GlueAccess
    attribute = DeclaredAttribute
    Response = GlueResponse
    RedirectResponse = GlueRedirectResponse

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
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
        form: ModelForm | None = None,
        forms: Mapping[str, ModelForm] | None = None,
        select_related: Sequence[str] | None = None,
    ) -> None:
        Glue.object(
            request=request,
            glue=ModelGlue(
                instance=target,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
                form=form,
                forms=forms,
                select_related=select_related,
            ),
        )

    @staticmethod
    def queryset(
        request: HttpRequest,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] = (),
        exclude: Sequence[str] = (),
        form: ModelForm | None = None,
        forms: Mapping[str, ModelForm] | None = None,
    ) -> None:
        Glue.object(
            request=request,
            glue=QuerySetGlue(
                queryset=target,
                name=unique_name,
                access=access,
                fields=fields,
                exclude=exclude,
                form=form,
                forms=forms,
            ),
        )

    @staticmethod
    def form(
        request: HttpRequest,
        unique_name: str,
        target: BaseForm,
        access: GlueAccess = GlueAccess.CHANGE,
    ) -> None:
        Glue.object(
            request=request,
            glue=FormGlue(
                form=target,
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
                name=unique_name,
                access=GlueAccess.VIEW,
            ),
        )

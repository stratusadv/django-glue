from django.http import HttpRequest
from typing import Sequence

from django.db.models import Model, QuerySet
from django.forms import ModelForm, BaseForm

from django_glue import Glue
from django_glue.access.access import GlueAccess


class GlueRequest:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request

    def model(
        self,
        unique_name: str,
        target: Model,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
        Glue.model(
            request=self.request,
            unique_name=unique_name,
            target=target,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs,
        )

    def queryset(
        self,
        unique_name: str,
        target: QuerySet,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence = (),
        exclude: Sequence[str] = (),
        form_class: type[ModelForm] | None = None,
        **kwargs,
    ) -> None:
        Glue.queryset(
            request=self.request,
            unique_name=unique_name,
            target=target,
            access=access,
            fields=fields,
            exclude=exclude,
            form_class=form_class,
            **kwargs,
        )

    def form(
        self, unique_name: str, target: BaseForm, access: GlueAccess = GlueAccess.VIEW, **kwargs
    ) -> None:
        Glue.form(
            request=self.request, unique_name=unique_name, target=target, access=access, **kwargs
        )

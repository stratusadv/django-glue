from __future__ import annotations
from typing import TYPE_CHECKING

from django.http import HttpRequest

from django_glue.shortcuts.glue import Glue

if TYPE_CHECKING:
    from test_project.gorilla.models import Gorilla


class GorillaService:
    def __init__(self, gorilla: Gorilla):
        self.gorilla = gorilla

    @Glue.action(access=Glue.Access.DELETE)
    def increment_age(self, request: HttpRequest):
        self.gorilla.age = self.gorilla.age + 1
        self.gorilla.save()
        return {
            'name': self.gorilla.name
        }

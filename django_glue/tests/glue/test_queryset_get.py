from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase

from django_glue.access import GlueAccess
from django_glue.exceptions import GlueModelInstanceNotFoundError
from django_glue.glue.objects.django.queryset import QuerySetGlue
from test_project.gorilla.models import Gorilla


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


def build_glue(queryset=None, **kwargs):
    kwargs.setdefault('fields', ['id', 'name'])
    glue_object = QuerySetGlue(
        Gorilla.objects.all() if queryset is None else queryset,
        name='gorillas',
        access=GlueAccess.VIEW,
        **kwargs,
    )
    glue_object.request = request_with_session()
    glue_object.policy

    return glue_object


class QuerySetGetTestCase(TestCase):
    def setUp(self):
        self.inside = Gorilla.objects.create(
            name='Inside', age=1, weight=100.0, height=1.5
        )
        self.outside = Gorilla.objects.create(
            name='Outside', age=2, weight=100.0, height=1.5
        )
        self.glue_object = build_glue(Gorilla.objects.filter(name='Inside'))

    def test_get_returns_payload_for_a_row_inside_the_queryset(self):
        result = self.glue_object.get(pk=self.inside.pk)

        assert result['state']['name']['value'] == 'Inside'

    def test_get_reports_not_found_for_a_row_outside_the_queryset(self):
        with self.assertRaises(GlueModelInstanceNotFoundError) as context:
            self.glue_object.get(pk=self.outside.pk)

        assert context.exception.status == 404
        assert context.exception.code == 'model_instance_not_found'
        assert context.exception.details() == {
            'model': 'gorilla.Gorilla',
            'pk': self.outside.pk,
        }

    def test_get_reports_not_found_for_a_pk_that_does_not_exist(self):
        with self.assertRaises(GlueModelInstanceNotFoundError):
            self.glue_object.get(pk=999999)

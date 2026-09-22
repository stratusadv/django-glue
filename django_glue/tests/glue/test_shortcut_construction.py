from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase

from django_glue import Glue
from django_glue.glue.context import GlueContextManager
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from test_project.gorilla.models import Gorilla
from test_project.test_forms import TestModelForm as GorillaModelForm


def request_with_session():
    return SimpleNamespace(
        session=SimpleNamespace(session_key='test-session', create=lambda: None),
        FILES={},
        __dict__={},
    )


class NonRegisteringConstructionTestCase(TestCase):
    """The family shortcuts serve two contexts (component-system.md §4).

    Their request-and-name form registers a page root from a view. Omitting the
    request returns a configured, unbound object for a child property or a
    callable result, where the response pipeline supplies request and address.
    """

    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Alpha', age=12)

    def test_model_without_a_request_is_configured_but_unregistered(self):
        glue_object = Glue.model(target=self.gorilla, fields=['name'])

        assert isinstance(glue_object, ModelGlue)
        assert glue_object.is_bound is False
        assert set(glue_object._included_fields) == {'id', 'name'}

    def test_queryset_without_a_request_is_configured_but_unregistered(self):
        glue_object = Glue.queryset(target=Gorilla.objects.all(), fields=['name'])

        assert isinstance(glue_object, QuerySetGlue)
        assert glue_object.is_bound is False

    def test_form_without_a_request_is_configured_but_unregistered(self):
        glue_object = Glue.form(target=GorillaModelForm(instance=self.gorilla))

        assert isinstance(glue_object, FormGlue)
        assert glue_object.is_bound is False

    def test_an_unregistered_object_stays_out_of_the_manifest_list(self):
        """The whole point: a child must not become a second page root."""
        request = request_with_session()
        Glue.model(request=request, unique_name='page_root', target=self.gorilla, fields=['name'])
        Glue.model(target=self.gorilla, fields=['name'])

        registered = GlueContextManager(request).glue_objects

        assert len(registered) == 1
        assert registered[0].name == 'page_root'

    def test_the_registering_form_still_binds_and_registers(self):
        request = request_with_session()

        glue_object = Glue.model(
            request=request,
            unique_name='gorilla',
            target=self.gorilla,
            fields=['name'],
        )

        assert glue_object.is_bound is True
        assert GlueContextManager(request).glue_objects == [glue_object]

    def test_positional_calls_are_unchanged(self):
        """Existing call sites pass request and name positionally."""
        request = request_with_session()

        glue_object = Glue.queryset(request, 'gorillas', Gorilla.objects.all(), fields=['name'])

        assert glue_object.is_bound is True
        assert glue_object.name == 'gorillas'


class ComponentChildConstructionTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Alpha', age=12)

    def test_a_callable_may_return_a_configured_model(self):
        """This is what replaces hand-rolled transport splicing."""
        class Card(Glue.Component):
            template = 'gorilla/component/gorilla_card.html'

            gorilla_id: int = Glue.attr(parameter=True)

            @Glue.attr(required_access=Glue.Access.CHANGE, takes_client_state=False)
            def edit(self) -> ModelGlue:
                return Glue.model(
                    target=Gorilla.objects.get(pk=self.gorilla_id),
                    access=Glue.Access.CHANGE,
                    fields=['name', 'age'],
                )

        component = Card(name='card', gorilla_id=self.gorilla.pk)
        component.request = request_with_session()

        result = component.edit()

        assert isinstance(result, ModelGlue)
        assert result.is_bound is False
        assert result.instance == self.gorilla

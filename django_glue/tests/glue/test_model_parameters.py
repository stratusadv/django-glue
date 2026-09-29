from __future__ import annotations

import datetime
import enum
import uuid
import warnings
from dataclasses import dataclass
from decimal import Decimal

import pytest
from django.db import models
from django.db.models.functions import Upper

from django_glue import Glue
from django_glue.exceptions import (
    GlueComponentParameterError,
    GlueModelInstanceNotFoundError,
    GlueModelParameterMismatchWarning,
)
from django_glue.glue.component import Component
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.gorilla.models import Gorilla


class GorillaCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.ComponentParameter
    def gorilla(self, pk: int) -> Gorilla:
        return Gorilla.objects.filter(age__lt=60).annotate(loud_name=Upper('name')).get(pk=pk)

    def get_context_data(self) -> dict[str, str]:
        return {'greeting': self.gorilla.loud_name}

    @Glue.attr
    def rename(self) -> None:
        Gorilla.objects.filter(pk=self.gorilla.pk).update(name='renamed')

    @Glue.attr
    def show(self, pk: int) -> None:
        self.gorilla = pk


def reconstruct(component: Component, attribute: str | None, **kwargs: object) -> tuple[Component, dict]:
    context = call_context(component, attribute, kwargs=kwargs)
    reconstructed = type(component).from_attribute_call_resolver_context(context)
    entry, _introduced = reconstructed.process_attribute_call(context)
    return reconstructed, entry


@pytest.fixture
def gorilla(db) -> Gorilla:
    return Gorilla.objects.create(name='Koko', age=20)


@pytest.fixture
def loaded_gorilla(gorilla) -> Gorilla:
    return Gorilla.objects.annotate(loud_name=Upper('name')).get(pk=gorilla.pk)


def test_supplied_instance_is_used_without_a_query(
    mock_request, loaded_gorilla, django_assert_num_queries, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = False
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))

    with django_assert_num_queries(0):
        assert component.gorilla is loaded_gorilla
        html = component.render().html

    assert '>KOKO</span>' in html
    assert component.identity['parameters'] == {'gorilla': loaded_gorilla.pk}


def test_supplied_key_is_resolved_through_the_initializer(mock_request, gorilla) -> None:
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=gorilla.pk))

    assert component.gorilla.loud_name == 'KOKO'


def test_reconstruction_resolves_the_signed_key_through_the_initializer(
    mock_request, loaded_gorilla,
) -> None:
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))

    _reconstructed, entry = reconstruct(component, 'rename')

    assert '>RENAMED</span>' in entry['html']


def test_row_that_left_the_initializer_scope_is_not_found(mock_request, loaded_gorilla) -> None:
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))
    Gorilla.objects.filter(pk=loaded_gorilla.pk).update(age=60)

    with pytest.raises(GlueModelInstanceNotFoundError) as caught:
        reconstruct(component, 'rename')

    assert caught.value.code == 'model_instance_not_found'


def test_assigning_a_key_retargets_and_rerenders(mock_request, loaded_gorilla) -> None:
    other = Gorilla.objects.create(name='Mjuku', age=10)
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))

    _reconstructed, entry = reconstruct(component, 'show', pk=other.pk)

    assert '>MJUKU</span>' in entry['html']
    assert GluePolicy.from_token(entry['policy_token']).identity['parameters'] == {'gorilla': other.pk}


def test_verification_rejects_an_instance_outside_the_initializer_scope(
    mock_request, db, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    elder = Gorilla.objects.create(name='Elder', age=60)
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=elder))

    with pytest.raises(GlueComponentParameterError, match='does not return'):
        _ = component.gorilla


def test_verification_warns_and_uses_the_initializer_instance_when_an_annotation_is_missing(
    mock_request, gorilla, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=gorilla))

    with pytest.warns(GlueModelParameterMismatchWarning, match='loud_name'):
        resolved = component.gorilla

    assert resolved.loud_name == 'KOKO'


def test_verification_accepts_an_instance_loaded_like_the_initializer(
    mock_request, loaded_gorilla, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))

    with warnings.catch_warnings():
        warnings.simplefilter('error', GlueModelParameterMismatchWarning)
        assert component.gorilla is loaded_gorilla


def test_model_parameter_is_not_client_callable(mock_request, loaded_gorilla) -> None:
    component = Glue.object(mock_request, GorillaCardComponent(gorilla=loaded_gorilla))

    static_data = component.get_static_data()

    assert 'gorilla' not in static_data['callables']
    assert 'gorilla' in static_data['fields']


def test_other_values_are_rejected_at_construction(mock_request, db) -> None:
    with pytest.raises(GlueComponentParameterError, match='takes a Gorilla'):
        GorillaCardComponent(gorilla=None)

    with pytest.raises(GlueComponentParameterError, match='saved Gorilla'):
        GorillaCardComponent(gorilla=Gorilla(name='Unsaved'))


def test_initializer_cycle_is_rejected(mock_request, gorilla) -> None:
    class CycleComponent(Component):
        template = 'glue_template_test.html'

        @Glue.ComponentParameter
        def first(self, pk: int) -> Gorilla:
            return self.second

        @Glue.ComponentParameter
        def second(self, pk: int) -> Gorilla:
            return self.first

    component = Glue.object(mock_request, CycleComponent(first=gorilla.pk, second=gorilla.pk))

    with pytest.raises(GlueComponentParameterError, match='cycle'):
        _ = component.first


def test_initializer_must_return_a_model() -> None:
    with pytest.raises(GlueComponentParameterError, match='Django model class'):
        class NotAModelComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter
            def label(self, pk: int) -> str:
                return str(pk)


def test_initializer_must_take_only_a_key() -> None:
    with pytest.raises(GlueComponentParameterError, match=r'def gorilla\(self, pk\)'):
        class WrongSignatureComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter
            def gorilla(self, pk: int, extra: int) -> Gorilla:
                return Gorilla.objects.get(pk=pk)


def test_decorator_form_takes_no_options() -> None:
    with pytest.raises(TypeError, match='takes no options'):
        class EditableComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter(editable=True)
            def gorilla(self, pk: int) -> Gorilla:
                return Gorilla.objects.get(pk=pk)


class Mood(enum.StrEnum):
    CALM = 'calm'
    RESTLESS = 'restless'


@dataclass(frozen=True, slots=True, kw_only=True)
class Window:
    start: datetime.date
    budget: Decimal
    mood: Mood


class WindowComponent(Component):
    template = 'glue_template_test.html'

    window: Window = Glue.ComponentParameter()


def test_dataclass_parameter_round_trips_through_the_token(mock_request) -> None:
    window = Window(start=datetime.date(2026, 9, 1), budget=Decimal('12.50'), mood=Mood.CALM)
    component = Glue.object(mock_request, WindowComponent(window=window))

    reconstructed, entry = reconstruct(component, None)

    assert component.identity['parameters'] == {
        'window': {'start': '2026-09-01', 'budget': '12.50', 'mood': 'calm'},
    }
    assert reconstructed.window == window
    assert 'html' in entry


class Receipt(models.Model):
    id = models.UUIDField(primary_key=True)

    class Meta:
        app_label = 'gorilla'
        managed = False


class ReceiptCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.ComponentParameter
    def receipt(self, pk: uuid.UUID) -> Receipt:
        return Receipt.objects.get(pk=pk)


def test_a_uuid_key_is_signed_as_a_string_and_read_back() -> None:
    key = uuid.uuid4()

    signed = ReceiptCardComponent(receipt=Receipt(pk=key)).identity['parameters']
    rebuilt = ReceiptCardComponent(**signed).identity['parameters']

    assert signed == rebuilt == {'receipt': str(key)}


@dataclass(frozen=True)
class Holder:
    gorilla: Gorilla


class HolderComponent(Component):
    template = 'glue_template_test.html'

    holder: Holder = Glue.ComponentParameter()


def test_dataclass_parameter_holding_a_model_is_rejected(db) -> None:
    with pytest.raises(GlueComponentParameterError):
        HolderComponent(holder=Holder(gorilla=Gorilla(name='x')))

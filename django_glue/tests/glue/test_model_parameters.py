from __future__ import annotations

import datetime
import enum
import inspect
import uuid
import warnings
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

import pytest
from django.db import models
from django.db.models.functions import Upper
from django.template import Context, Template

from django_glue import Glue
from django_glue.exceptions import (
    GlueComponentParameterError,
    GlueModelInstanceNotFoundError,
    GlueModelParameterMismatchWarning,
)
from django_glue.glue.components import Component, component_registry
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill


class GorillaCardComponent(Component):
    template = 'glue_component_greeting_test.html'

    @Glue.ComponentParameter
    def gorilla(self, pk: int) -> Gorilla:
        return Gorilla.objects.filter(age__lt=60).annotate(loud_name=Upper('name')).get(pk=pk)

    @property
    def greeting(self) -> str:
        return self.gorilla.loud_name

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


class GorillaRecordComponent(Component):
    template = 'glue_template_test.html'

    @Glue.ComponentParameter
    def gorilla(self, pk: int) -> Gorilla:
        return Gorilla.objects.prefetch_related('skills', 'fights_as_red_corner').get(pk=pk)


class FightCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.ComponentParameter
    def fight(self, pk: int) -> Fight:
        return Fight.objects.select_related('red_corner').prefetch_related('red_corner__skills').get(pk=pk)


def test_verification_names_a_missing_prefetch_although_another_is_loaded(
    mock_request, gorilla, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    partly_loaded = Gorilla.objects.prefetch_related('skills').get(pk=gorilla.pk)
    component = Glue.object(mock_request, GorillaRecordComponent(gorilla=partly_loaded))

    with pytest.warns(GlueModelParameterMismatchWarning) as caught:
        _ = component.gorilla

    [warning] = caught
    assert 'without fights_as_red_corner,' in str(warning.message)
    assert '_prefetched_objects_cache' not in str(warning.message)


def test_verification_names_a_missing_nested_load_by_its_path(mock_request, gorilla, settings) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    fight = Fight.objects.create(name='Bout', red_corner=gorilla, blue_corner=gorilla)
    shallow = Fight.objects.select_related('red_corner').get(pk=fight.pk)
    component = Glue.object(mock_request, FightCardComponent(fight=shallow))

    with pytest.warns(GlueModelParameterMismatchWarning, match='without red_corner__skills,'):
        _ = component.fight


class Champion(models.Model):
    class Meta:
        app_label = 'gorilla'
        managed = False


class Belt(models.Model):
    holder = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='belt')

    class Meta:
        app_label = 'gorilla'
        managed = False


def belt_held_by_a_champion(pk: int, **champion_annotations: Any) -> Belt:
    """A belt as ``select_related('holder')`` loads it: each side of a one-to-one caches the other."""
    belt = Belt(pk=pk, holder_id=pk)
    champion = Champion(pk=pk)
    vars(champion).update(champion_annotations)
    Belt.holder.field.set_cached_value(belt, champion)
    Belt.holder.field.remote_field.set_cached_value(champion, belt)
    return belt


class BeltCardComponent(Component):
    template = 'glue_template_test.html'

    @Glue.ComponentParameter
    def belt(self, pk: int) -> Belt:
        return belt_held_by_a_champion(pk, title_count=3)


def test_verification_accepts_a_one_to_one_whose_sides_cache_each_other(mock_request, settings) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    supplied = belt_held_by_a_champion(1, title_count=3)
    component = Glue.object(mock_request, BeltCardComponent(belt=supplied))

    with warnings.catch_warnings():
        warnings.simplefilter('error', GlueModelParameterMismatchWarning)
        assert component.belt is supplied


def test_verification_names_a_missing_load_across_a_one_to_one(mock_request, settings) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    component = Glue.object(mock_request, BeltCardComponent(belt=belt_held_by_a_champion(1)))

    with pytest.warns(GlueModelParameterMismatchWarning, match='without holder__title_count,'):
        _ = component.belt


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


def test_initializer_must_take_a_key_or_a_model_and_a_key() -> None:
    signatures = r'def gorilla\(self, pk\) or def gorilla\(self, model, pk\)'
    with pytest.raises(GlueComponentParameterError, match=signatures):
        class WrongSignatureComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter
            def gorilla(self, model: type[Gorilla], pk: int, extra: int) -> Gorilla:
                return Gorilla.objects.get(pk=pk)


def test_decorator_form_takes_no_options() -> None:
    with pytest.raises(TypeError, match='takes no options'):
        class EditableComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter(editable=True)
            def gorilla(self, pk: int) -> Gorilla:
                return Gorilla.objects.get(pk=pk)


class Primate(models.Model):
    class Meta:
        abstract = True
        app_label = 'gorilla'


class NamedRowComponent(Component):
    template = 'glue_component_greeting_test.html'

    @Glue.ComponentParameter
    def row(self, model: type[models.Model], pk: int) -> models.Model:
        return model._default_manager.get(pk=pk)

    @property
    def greeting(self) -> str:
        return self.row.name

    @Glue.attr
    def show(self, model: str, pk: int) -> None:
        self.row = {'model': model, 'pk': pk}


class YoungGorillaCardComponent(Component):
    template = 'glue_component_greeting_test.html'

    @Glue.ComponentParameter
    def gorilla(self, model: type[Gorilla], pk: int) -> Gorilla:
        return model._default_manager.filter(age__lt=60).get(pk=pk)

    @property
    def greeting(self) -> str:
        return self.gorilla.name


@pytest.fixture
def skill(db) -> Skill:
    return Skill.objects.create(name='Grapple')


def test_bounded_parameter_signs_the_model_label_with_the_key(
    mock_request, gorilla, django_assert_num_queries, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = False
    component = Glue.object(mock_request, NamedRowComponent(row=gorilla))

    with django_assert_num_queries(0):
        assert component.row is gorilla
        html = component.render().html

    assert '>Koko</span>' in html
    assert component.identity['parameters'] == {
        'row': {'model': 'gorilla.gorilla', 'pk': gorilla.pk},
    }


def test_bounded_parameter_reconstructs_each_model_through_the_initializer(
    mock_request, gorilla, skill,
) -> None:
    for row, name in ((gorilla, 'Koko'), (skill, 'Grapple')):
        component = Glue.object(mock_request, NamedRowComponent(row=row))

        reconstructed, entry = reconstruct(component, None)

        assert type(reconstructed.row) is type(row)
        assert f'>{name}</span>' in entry['html']


def test_assigning_a_signed_value_retargets_a_bounded_parameter_to_another_model(
    mock_request, gorilla, skill,
) -> None:
    component = Glue.object(mock_request, NamedRowComponent(row=gorilla))

    _reconstructed, entry = reconstruct(component, 'show', model='gorilla.skill', pk=skill.pk)

    assert '>Grapple</span>' in entry['html']
    assert GluePolicy.from_token(entry['policy_token']).identity['parameters'] == {
        'row': {'model': 'gorilla.skill', 'pk': skill.pk},
    }


def test_bounded_parameter_rejects_a_model_outside_its_bound(skill) -> None:
    with pytest.raises(GlueComponentParameterError, match='not a Gorilla'):
        YoungGorillaCardComponent(gorilla={'model': 'gorilla.skill', 'pk': skill.pk})

    with pytest.raises(GlueComponentParameterError, match='takes a Gorilla'):
        YoungGorillaCardComponent(gorilla=skill)


def test_bounded_parameter_rejects_an_unknown_model_label(db) -> None:
    with pytest.raises(GlueComponentParameterError, match='no installed model'):
        NamedRowComponent(row={'model': 'gorilla.okapi', 'pk': 1})


def test_bounded_parameter_rejects_a_bare_key(gorilla) -> None:
    with pytest.raises(GlueComponentParameterError, match='signed model and key'):
        NamedRowComponent(row=gorilla.pk)


def test_bounded_row_that_left_the_initializer_scope_is_not_found(mock_request, gorilla) -> None:
    component = Glue.object(mock_request, YoungGorillaCardComponent(gorilla=gorilla))
    Gorilla.objects.filter(pk=gorilla.pk).update(age=60)

    with pytest.raises(GlueModelInstanceNotFoundError) as caught:
        reconstruct(component, None)

    assert caught.value.code == 'model_instance_not_found'


def test_bounded_verification_resolves_a_supplied_instance_through_its_own_model(
    mock_request, db, settings,
) -> None:
    settings.DJANGO_GLUE_VERIFY_MODEL_PARAMETERS = True
    elder = Gorilla.objects.create(name='Elder', age=60)
    component = Glue.object(mock_request, YoungGorillaCardComponent(gorilla=elder))

    with pytest.raises(GlueComponentParameterError, match='does not return'):
        _ = component.gorilla


def test_concrete_parameter_rejects_an_abstract_model() -> None:
    with pytest.raises(GlueComponentParameterError, match=r'def primate\(self, model, pk\)'):
        class AbstractComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter
            def primate(self, pk: int) -> Primate:
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


class GorillaEditorComponent(Component):
    template = 'glue_component_greeting_test.html'

    starting_age: int = Glue.ComponentParameter()

    @Glue.ComponentParameter
    def gorilla(self, pk: int | None) -> Gorilla:
        if pk is None:
            return Gorilla(name='New gorilla', age=self.starting_age)
        return Gorilla.objects.get(pk=pk)

    @property
    def greeting(self) -> str:
        return f'{self.gorilla.name}, {self.gorilla.age}'

    @Glue.attr
    def save(self) -> None:
        self.gorilla.save()

    @Glue.attr
    def rename(self, name: str) -> None:
        self.gorilla.name = name
        self.gorilla.save()

    @Glue.attr
    def look(self) -> None:
        return None

    @Glue.attr(skip_rerender=True)
    def save_quietly(self) -> None:
        self.gorilla.save()


def test_leaving_the_parameter_out_builds_a_draft_through_the_initializer(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(starting_age=7))

    assert component.gorilla.pk is None
    assert (component.gorilla.name, component.gorilla.age) == ('New gorilla', 7)
    assert component.identity['parameters'] == {'starting_age': 7, 'gorilla': None}


def test_passing_none_builds_the_same_draft_as_leaving_the_parameter_out(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(gorilla=None, starting_age=7))

    assert component.gorilla.pk is None
    assert component.identity['parameters'] == {'starting_age': 7, 'gorilla': None}


def test_a_draft_parameter_is_optional_in_the_component_signature() -> None:
    parameters = inspect.signature(GorillaEditorComponent).parameters

    assert parameters['gorilla'].default is None
    assert parameters['starting_age'].default is inspect.Parameter.empty


def test_a_draft_is_rebuilt_from_its_null_key_and_its_seed_on_a_later_request(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(starting_age=7))

    reconstructed, entry = reconstruct(component, 'look')

    assert reconstructed.gorilla.pk is None
    assert '>New gorilla, 7</span>' in entry['html']
    assert not Gorilla.objects.exists()


def test_saving_a_draft_signs_its_new_key_and_rerenders(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(gorilla=None, starting_age=7))

    _reconstructed, entry = reconstruct(component, 'save')

    saved = Gorilla.objects.get()
    assert GluePolicy.from_token(entry['policy_token']).identity['parameters']['gorilla'] == saved.pk
    assert '>New gorilla, 7</span>' in entry['html']


def test_a_saved_draft_is_edited_not_created_again_on_the_next_request(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(gorilla=None, starting_age=7))
    _reconstructed, entry = reconstruct(component, 'save')
    signed = GluePolicy.from_token(entry['policy_token']).identity['parameters']

    saved_component = Glue.object(mock_request, GorillaEditorComponent(**signed))
    _reconstructed, entry = reconstruct(saved_component, 'rename', name='Koko')

    assert list(Gorilla.objects.values_list('name', flat=True)) == ['Koko']
    assert '>Koko, 7</span>' in entry['html']


def test_saving_a_draft_rerenders_although_the_callable_skips_rerender(mock_request, db) -> None:
    component = Glue.object(mock_request, GorillaEditorComponent(gorilla=None, starting_age=7))

    _reconstructed, entry = reconstruct(component, 'save_quietly')

    saved = Gorilla.objects.get()
    assert GluePolicy.from_token(entry['policy_token']).identity['parameters']['gorilla'] == saved.pk
    assert 'html' in entry


@dataclass(frozen=True, slots=True, kw_only=True)
class GorillaSeed:
    name: str
    born: datetime.date


class SeededGorillaEditorComponent(Component):
    template = 'glue_component_greeting_test.html'

    seed: GorillaSeed | None = Glue.ComponentParameter(None)
    extras: dict[str, Any] = Glue.ComponentParameter(default_factory=dict)

    @Glue.ComponentParameter
    def gorilla(self, pk: int | None) -> Gorilla:
        if pk is None:
            return Gorilla(name=self.seed.name, description=f'Born {self.seed.born:%Y}', **self.extras)
        return Gorilla.objects.get(pk=pk)

    @property
    def greeting(self) -> str:
        return f'{self.gorilla.name}, {self.gorilla.description}, {self.gorilla.age}'

    @Glue.attr
    def look(self) -> None:
        return None


def test_a_draft_is_seeded_from_a_dataclass_and_a_dict_parameter_on_every_request(mock_request, db) -> None:
    component = Glue.object(mock_request, SeededGorillaEditorComponent(
        seed=GorillaSeed(name='Koko', born=datetime.date(2019, 7, 4)),
        extras={'age': 7},
    ))

    reconstructed, entry = reconstruct(component, 'look')

    assert reconstructed.seed == GorillaSeed(name='Koko', born=datetime.date(2019, 7, 4))
    assert '>Koko, Born 2019, 7</span>' in entry['html']


def test_the_seed_parameters_are_left_out_when_editing_a_saved_row(mock_request, gorilla) -> None:
    component = Glue.object(mock_request, SeededGorillaEditorComponent(gorilla=gorilla))

    assert component.gorilla == gorilla
    assert component.identity['parameters'] == {'seed': None, 'extras': {}, 'gorilla': gorilla.pk}


def test_a_draft_parameter_still_takes_a_saved_row_or_its_key(mock_request, gorilla) -> None:
    by_instance = Glue.object(mock_request, GorillaEditorComponent(gorilla=gorilla, starting_age=7))
    by_key = Glue.object(mock_request, GorillaEditorComponent(gorilla=gorilla.pk, starting_age=7))

    assert by_instance.identity['parameters']['gorilla'] == gorilla.pk
    assert by_key.gorilla == gorilla


def test_a_draft_parameter_rejects_an_unsaved_instance_naming_the_fix(db) -> None:
    with pytest.raises(GlueComponentParameterError, match='leave the parameter out'):
        GorillaEditorComponent(gorilla=Gorilla(name='Prepared'), starting_age=7)


def test_a_parameter_that_does_not_accept_a_draft_is_still_required(db) -> None:
    with pytest.raises(GlueComponentParameterError, match='Missing parameters'):
        GorillaCardComponent()


def test_a_stamp_that_leaves_the_parameter_out_renders_the_draft(mock_request, db) -> None:
    component_registry.by_tag_name['gorilla_editor'] = GorillaEditorComponent
    try:
        html = Template(
            "{% load django_glue %}{% glue_component 'gorilla_editor' starting_age=7 %}"
        ).render(Context({'request': mock_request}))
    finally:
        del component_registry.by_tag_name['gorilla_editor']
    entry = GlueContextManager(mock_request).serialized_objects[0]

    assert '>New gorilla, 7</span>' in html
    assert GluePolicy.from_token(entry['policy_token']).identity['parameters'] == {
        'starting_age': 7,
        'gorilla': None,
    }


def test_optional_spelling_of_the_key_annotation_accepts_a_draft(db) -> None:
    class OptionalKeyComponent(Component):
        template = 'glue_template_test.html'

        @Glue.ComponentParameter
        def gorilla(self, pk: Optional[int]) -> Gorilla:  # noqa: UP045
            return Gorilla() if pk is None else Gorilla.objects.get(pk=pk)

    assert OptionalKeyComponent(gorilla=None).gorilla.pk is None


def test_a_key_annotation_without_none_does_not_accept_a_draft(db) -> None:
    with pytest.raises(GlueComponentParameterError, match=r'annotate its key as int \| None'):
        GorillaCardComponent(gorilla=None)


def test_a_bounded_parameter_cannot_declare_a_draft() -> None:
    with pytest.raises(GlueComponentParameterError, match='does not accept a draft'):
        class BoundedDraftComponent(Component):
            template = 'glue_template_test.html'

            @Glue.ComponentParameter
            def row(self, model: type[models.Model], pk: int | None) -> models.Model:
                return model() if pk is None else model._default_manager.get(pk=pk)


@pytest.mark.parametrize('value', [
    {'model': 'gorilla.gorilla', 'pk': None},
    {'model': 5, 'pk': 1},
    {'model': None, 'pk': 1},
])
def test_bounded_parameter_rejects_a_malformed_signed_value(db, value) -> None:
    with pytest.raises(GlueComponentParameterError):
        NamedRowComponent(row=value)

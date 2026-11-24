"""A child is declared and read as its Django value (ADR 050)."""

from __future__ import annotations

from typing import Any

import pytest
from django import forms

from django_glue import Glue
from django_glue.glue.components import Component
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.components.test_child_paths import token_of
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.gorilla.models import Skill


class FilterForm(forms.Form):
    search = forms.CharField(required=False)
    limit = forms.IntegerField(required=False)


class WordForm(forms.Form):
    search = forms.CharField(required=False)

    def __init__(self, *args: Any, word: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.word = word


class ListingComponent(Component):
    template = 'glue_component_greeting_test.html'

    @Glue.child(access=Glue.Access.CHANGE)
    def filters(self) -> FilterForm:
        return FilterForm(initial={'search': 'jab'})

    @Glue.child
    def notes(self) -> FilterForm:
        return FilterForm()

    @Glue.child(editable=['search'])
    def narrowed(self) -> FilterForm:
        return FilterForm()

    @Glue.child
    def kept(self) -> Glue.Form:
        return Glue.form(
            target=WordForm(word='hook', initial={'search': 'jab'}),
            access=Glue.Access.CHANGE,
            form_kwargs={'word': 'hook'},
        )

    @property
    def greeting(self) -> str:
        filters = self.filters
        filters.is_valid()
        return f'search={filters.cleaned_data.get("search") or ""}'

    @Glue.attr(skip_rerender=True)
    def read(self) -> dict[str, Any]:
        form = self.filters
        return {
            'is_form': type(form) is FilterForm,
            'is_bound': form.is_bound,
            'initial': form.initial,
            'valid': form.is_valid(),
            'search': form.cleaned_data.get('search'),
            'read_once': form is self.filters,
        }

    @Glue.attr(skip_rerender=True)
    def read_kept(self) -> dict[str, Any]:
        form = self.kept
        form.is_valid()
        return {'is_form': type(form) is WordForm, 'word': form.word, 'search': form.cleaned_data['search']}

    @Glue.attr
    def check(self) -> bool:
        return self.filters.is_valid()

    @Glue.attr
    def touch(self) -> None:
        pass


@pytest.fixture
def listing(mock_request) -> ListingComponent:
    return Glue.object(mock_request, ListingComponent(access=Glue.Access.VIEW))


def submission(listing: ListingComponent, path: str, **updates: Any) -> dict[str, Any]:
    """What the browser submits for one of the list's children, with these changes."""
    return {path: {'policy_token': token_of(listing, path), 'updates': updates}}


def call(
    listing: ListingComponent,
    attribute: str | None,
    submissions: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = call_context(listing, attribute).model_copy(update={'child_submissions': submissions or {}})
    rebuilt = ListingComponent.from_attribute_call_resolver_context(context)
    return rebuilt.process_attribute_call(context)


def child_entry(listing: ListingComponent, introduced: list[dict[str, Any]], path: str) -> dict[str, Any]:
    address = listing.policy.children[path]
    return next(item for item in introduced if item['address'] == address)


def test_a_bare_form_child_is_a_form_glue_under_its_name_with_the_decorators_access(listing) -> None:
    policy = GluePolicy.from_token(token_of(listing, 'filters'))

    assert policy.namespace == FormGlue.namespace
    assert policy.name == 'filters'
    assert policy.access == Glue.Access.CHANGE


def test_a_bare_child_with_no_access_has_its_owners(listing) -> None:
    assert GluePolicy.from_token(token_of(listing, 'notes')).access == Glue.Access.VIEW


def test_a_bare_form_child_takes_the_decorators_editable(mock_request) -> None:
    listing = Glue.object(mock_request, ListingComponent(access=Glue.Access.CHANGE))

    assert GluePolicy.from_token(token_of(listing, 'narrowed')).identity['editable'] == ['search']
    assert GluePolicy.from_token(token_of(listing, 'notes')).identity['editable'] == ['search', 'limit']


def test_a_child_that_returns_a_glue_object_keeps_its_access(mock_request) -> None:
    listing = Glue.object(mock_request, ListingComponent(access=Glue.Access.VIEW))

    assert GluePolicy.from_token(token_of(listing, 'kept')).access == Glue.Access.CHANGE


def test_a_bare_child_compiles_a_slot_for_its_glue_object() -> None:
    class OptionalFilters(Component):
        template = 'glue_template_test.html'

        @Glue.child
        def filters(self) -> FilterForm | None:
            return None

    options = OptionalFilters.__dict__['filters'].__glue_options__
    assert options.expected_type is FormGlue
    assert options.is_nullable


@pytest.mark.parametrize(
    ('options', 'annotation', 'match'),
    [
        ({'fields': ['search']}, FilterForm, 'takes access, editable, not fields'),
        ({'fields': ['search']}, FormGlue, 'takes access, editable, not fields'),
        ({'access': Glue.Access.CHANGE}, Glue.FormSet, 'takes no options'),
        ({}, Skill, 'needs a return annotation'),
        ({}, int, 'needs a return annotation'),
    ],
)
def test_a_declaration_glue_cannot_honour_is_refused_when_the_class_is_defined(options, annotation, match) -> None:
    def filters(self): ...

    filters.__annotations__['return'] = annotation

    with pytest.raises(TypeError, match=match):
        Glue.child(**options)(filters)


def test_a_returned_glue_object_under_a_decorator_with_options_is_refused(mock_request) -> None:
    class TwiceSetComponent(Component):
        template = 'glue_template_test.html'

        @Glue.child(access=Glue.Access.CHANGE)
        def filters(self) -> FilterForm:
            return Glue.form(target=FilterForm(), access=Glue.Access.CHANGE)

    with pytest.raises(TypeError, match='a setting has one place'):
        Glue.object(mock_request, TwiceSetComponent()).render()


def test_the_first_render_reads_the_form_bound_to_its_initial(listing) -> None:
    assert '>search=jab</span>' in listing.render().html


def test_a_call_reads_the_form_bound_to_the_submission_with_its_initial(listing) -> None:
    entry, _ = call(listing, 'read', submission(listing, 'filters', search='ko'))

    assert entry['result'] == {
        'is_form': True,
        'is_bound': True,
        'initial': {'search': 'jab'},
        'valid': True,
        'search': 'ko',
        'read_once': True,
    }


def test_a_call_with_nothing_submitted_reads_the_form_bound_to_its_initial(listing) -> None:
    entry, _ = call(listing, 'read')

    assert entry['result']['is_bound'] is True
    assert entry['result']['search'] == 'jab'


def test_a_render_call_reads_the_submitted_form(listing) -> None:
    entry, _ = call(listing, 'render', submission(listing, 'filters', search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_a_refresh_reads_the_submitted_form(listing) -> None:
    entry, _ = call(listing, None, submission(listing, 'filters', search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_the_re_render_after_a_call_reads_the_submitted_form(listing) -> None:
    entry, _ = call(listing, 'touch', submission(listing, 'filters', search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_errors_from_validating_the_read_form_reach_the_browser_after_a_call(listing) -> None:
    entry, introduced = call(listing, 'check', submission(listing, 'filters', limit='many'))

    assert entry['result'] is False
    value_attributes = child_entry(listing, introduced, 'filters')['computed_data']['value_attributes']
    assert value_attributes['limit']['errors']
    assert value_attributes['search']['errors'] == []


def test_errors_from_validating_the_read_form_reach_the_browser_after_a_refresh(listing) -> None:
    _, introduced = call(listing, None, submission(listing, 'filters', limit='many'))

    value_attributes = child_entry(listing, introduced, 'filters')['computed_data']['value_attributes']
    assert value_attributes['limit']['errors']


def test_a_child_that_returns_glue_form_reads_as_the_form_with_its_kept_arguments(listing) -> None:
    entry, _ = call(listing, 'read_kept', submission(listing, 'kept', search='ko'))

    assert entry['result'] == {'is_form': True, 'word': 'hook', 'search': 'ko'}


def test_a_child_that_returns_glue_form_reads_as_the_form_with_nothing_submitted(listing) -> None:
    entry, _ = call(listing, 'read_kept')

    assert entry['result'] == {'is_form': True, 'word': 'hook', 'search': 'jab'}

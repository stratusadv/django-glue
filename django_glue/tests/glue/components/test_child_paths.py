"""A component sees each child the user changed on every path (ADR 049)."""

from __future__ import annotations

from typing import Any

import pytest
from django import forms

from django_glue import Glue
from django_glue.exceptions import GlueRequestError
from django_glue.glue.components import Component
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context

INITIALIZED: list[str] = []


class FilterForm(forms.Form):
    search = forms.CharField(required=False)
    limit = forms.IntegerField(required=False)


class FilteredListComponent(Component):
    template = 'glue_component_greeting_test.html'

    @Glue.child
    def filters(self) -> Glue.Form:
        INITIALIZED.append('filters')
        return Glue.form(target=FilterForm(), access=Glue.Access.CHANGE)

    @Glue.child
    def terms(self) -> Glue.Form:
        return Glue.form(target=FilterForm(), access=Glue.Access.VIEW)

    @property
    def greeting(self) -> str:
        filters = self.filters
        _ = self.terms
        filters.is_valid()
        return f'search={filters.cleaned_data.get("search") or ""}'

    @Glue.attr(skip_rerender=True)
    def load_items(self) -> str:
        return self.greeting

    @Glue.attr
    def touch(self) -> None:
        pass

    @Glue.attr
    def narrow(self) -> None:
        # Application code reads the form, which changes no token (ADR 050), so the change is
        # made where Glue keeps the child.
        self._submitted_child('filters').attributes['search'].apply_update('narrowed')

    @Glue.attr
    def check(self) -> bool:
        return self.filters.is_valid()

    @Glue.attr(skip_rerender=True)
    def reads_twice(self) -> bool:
        return self.filters is self.filters


@pytest.fixture
def listing(mock_request) -> FilteredListComponent:
    # The child is at CHANGE under an owner at VIEW (ADR 028).
    return Glue.object(mock_request, FilteredListComponent(access=Glue.Access.VIEW))


@pytest.fixture(autouse=True)
def _forget_initializations() -> None:
    INITIALIZED.clear()


def token_of(listing: FilteredListComponent, path: str) -> str:
    address = listing.policy.children[path]
    return next(
        entry['policy_token']
        for entry in listing._serialized_child_entries()
        if entry['address'] == address
    )


def filters_submission(listing: FilteredListComponent, **updates: Any) -> dict[str, Any]:
    """What the browser submits for the list's filters, with these changes."""
    return {'filters': {'policy_token': token_of(listing, 'filters'), 'updates': updates}}


def call(
    listing: FilteredListComponent,
    attribute: str | None,
    submissions: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = call_context(listing, attribute).model_copy(
        update={'child_submissions': submissions or {}},
    )
    rebuilt = FilteredListComponent.from_attribute_call_resolver_context(context)
    return rebuilt.process_attribute_call(context)


def test_the_first_render_reads_the_initializers_child(listing) -> None:
    assert '>search=</span>' in listing.render().html


def test_a_call_reads_the_submitted_child(listing) -> None:
    entry, _ = call(listing, 'load_items', filters_submission(listing, search='ko'))

    assert entry['result'] == 'search=ko'


def test_a_render_call_reads_the_submitted_child(listing) -> None:
    entry, _ = call(listing, 'render', filters_submission(listing, search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_two_reads_in_a_call_with_a_submission_are_one_object(listing) -> None:
    entry, _ = call(listing, 'reads_twice', filters_submission(listing, search='ko'))

    assert entry['result'] is True


def test_the_re_render_after_a_call_carries_a_child_the_call_did_not_read(listing) -> None:
    entry, _ = call(listing, 'touch', filters_submission(listing, search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_the_re_render_after_a_call_reads_a_child_as_the_call_left_it(listing) -> None:
    entry, _ = call(listing, 'narrow', filters_submission(listing, search='ko'))

    assert '>search=narrowed</span>' in entry['html']


def test_the_re_render_does_not_answer_twice_for_a_child_the_call_read(listing) -> None:
    entry, introduced = call(listing, 'check', filters_submission(listing, limit='many'))

    assert entry['result'] is False
    filters_address = listing.policy.children['filters']
    [filters_entry] = [item for item in introduced if item['address'] == filters_address]
    assert filters_entry['computed_data']['value_attributes']['limit']['errors']


def test_a_refresh_reads_the_submitted_child(listing) -> None:
    entry, _ = call(listing, None, filters_submission(listing, search='ko'))

    assert '>search=ko</span>' in entry['html']


def test_a_refresh_answers_with_the_child_it_read(listing) -> None:
    _, introduced = call(listing, None, filters_submission(listing, search='ko'))

    filters_address = listing.policy.children['filters']
    assert [item['address'] for item in introduced].count(filters_address) == 1


def test_a_refresh_refuses_a_token_from_another_slot(listing) -> None:
    submissions = {'filters': {'policy_token': token_of(listing, 'terms'), 'updates': {}}}

    with pytest.raises(GlueRequestError):
        call(listing, None, submissions)


def test_a_refresh_refuses_a_malformed_token(listing) -> None:
    with pytest.raises(GlueRequestError):
        call(listing, None, {'filters': {'policy_token': 'not-a-token'}})


def test_a_refresh_refuses_a_view_child(listing) -> None:
    terms_token = token_of(listing, 'terms')
    submissions = {'terms': {'policy_token': terms_token, 'updates': {'search': 'ko'}}}

    with pytest.raises(GlueRequestError):
        call(listing, None, submissions)


def test_a_child_read_twice_with_no_submission_is_built_once(listing) -> None:
    context = call_context(listing, 'reads_twice')
    INITIALIZED.clear()

    rebuilt = FilteredListComponent.from_attribute_call_resolver_context(context)
    entry, _ = rebuilt.process_attribute_call(context)

    assert entry['result'] is True
    assert INITIALIZED == ['filters']


class OptionalFiltersComponent(Component):
    template = 'glue_template_test.html'

    @Glue.child
    def filters(self) -> Glue.Form | None:
        return Glue.form(target=FilterForm(), access=Glue.Access.CHANGE)

    @Glue.attr
    def read(self) -> bool:
        return self.filters is self.filters


@pytest.mark.parametrize('reintroduce', [[], ['filters']])
def test_a_child_the_call_read_is_still_bound_once(mock_request, reintroduce) -> None:
    optional = Glue.object(mock_request, OptionalFiltersComponent())
    context = call_context(optional, 'read', reintroduce=reintroduce)

    rebuilt = OptionalFiltersComponent.from_attribute_call_resolver_context(context)
    entry, introduced = rebuilt.process_attribute_call(context)

    assert entry['result'] is True
    assert 'html' in entry
    # The token is omitted when unchanged, which keeps the children map too.
    successor = entry.get('policy_token', optional.policy.token)
    assert GluePolicy.from_token(successor).children == optional.policy.children
    assert len(introduced) == len({item['address'] for item in introduced})

"""Morph spike.

Measures what actually survives when server-rendered HTML is re-applied to a
live DOM region, under the three strategies available to django-glue:

  replace    -- element.outerHTML = html   (Glue's behavior before HTML unification)
  idiomorph  -- framework-agnostic morph, id-set matching
  alpine     -- @alpinejs/morph, Alpine-aware, keyed on the `key` attribute

The region is shaped like a component tree: one root element, cards carrying a
stable id/key (the address analogue), local Alpine state, a focusable input, and
a subtree owned by imperative third-party JS.

Cases that fail by design are strict xfails with the reason recorded; they are
the evidence behind design/reactive-system/component-system.md. An XPASS means a
library's behaviour changed and that evidence table is out of date.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

if TYPE_CHECKING:
    from _pytest.mark.structures import ParameterSet
    from playwright.sync_api import Locator, Page
    from pytest_django.live_server_helper import LiveServer

os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

pytestmark = [pytest.mark.e2e]

STRATEGIES = ('replace', 'idiomorph', 'alpine')

REPLACE_REBUILDS = 'replace rebuilds every node, discarding local Alpine state'
IDIOMORPH_DESYNCS = (
    'idiomorph patches the DOM back to the server HTML and Alpine does not re-run '
    'its effects, so the rendered output desyncs from Alpine state'
)


def expected_failure(strategy: str, reason: str) -> ParameterSet:
    # raises=AssertionError keeps infrastructure failures (a page that never
    # loads, a script that never registers) from hiding inside an xfail.
    return pytest.param(
        strategy,
        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason),
    )


def card(page: Page, key: str) -> Locator:
    return page.locator(f'#card-{key}')


def role(page: Page, key: str, name: str) -> Locator:
    return card(page, key).locator(f'[data-role="{name}"]')


def open_lab(page: Page, live_server: LiveServer, strategy: str) -> None:
    page.goto(f'{live_server.url}/lab/morph/')
    page.wait_for_function('window.Alpine && window.Idiomorph')
    # Alpine.morph is deferred; make sure it registered before selecting it.
    page.wait_for_function('window.Alpine.morph !== undefined')
    page.select_option('[data-role="strategy"]', strategy)


def dirty_the_dom(page: Page) -> None:
    """Put local state on the alpha card that exists nowhere in the server render."""
    role(page, 'alpha', 'toggle').click()
    role(page, 'alpha', 'bump').click()
    role(page, 'alpha', 'bump').click()
    role(page, 'alpha', 'note').fill('typed by the user')
    expect(role(page, 'alpha', 'details')).to_be_visible()
    expect(role(page, 'alpha', 'counter')).to_have_text('2')


def apply_and_settle(page: Page, action: str = 'rerender') -> None:
    before = page.evaluate('window.__morphApplied || 0')
    page.locator(f'[data-role="{action}"]').click()
    page.wait_for_function(f'(window.__morphApplied || 0) > {before}')


def apply_without_stealing_focus(page: Page, **options) -> None:
    """Trigger a re-render without clicking, so activeElement is not disturbed.

    Clicking the button focuses the button, which would make any focus
    assertion afterwards meaningless.
    """
    before = page.evaluate('window.__morphApplied || 0')
    page.evaluate('options => window.__morphLab.apply(options)', options)
    page.wait_for_function(f'(window.__morphApplied || 0) > {before}')


def mount_sequence(page: Page) -> list[str]:
    """Map each card's key to the mount-order of the DOM node now carrying it.

    Lets a reorder be classified: if the morph relocated live nodes the
    sequence numbers travel with their keys; if it repurposed nodes
    positionally, the numbers stay in document order and the keys slide
    across them -- taking the wrong Alpine scope with them.
    """
    return page.evaluate(
        '() => Array.from(document.querySelectorAll("#morph-region [data-key]"))'
        '.map(n => n.dataset.key + ":" + n.__mountSeq)'
    )


# --------------------------------------------------------------------------
# 1. Does the server render actually land? (a morph that preserves everything
#    including stale content would pass every other test and be useless)
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', STRATEGIES)
def test_server_content_updates(page: Page, live_server: LiveServer, strategy: str) -> None:
    open_lab(page, live_server, strategy)
    expect(role(page, 'alpha', 'server-value')).to_have_text('alpha-v1')

    apply_and_settle(page)

    expect(role(page, 'alpha', 'server-value')).to_have_text('alpha-v2')


# --------------------------------------------------------------------------
# 2. Local Alpine state: the whole reason morphing is on the table
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', [
    expected_failure('replace', REPLACE_REBUILDS),
    expected_failure('idiomorph', IDIOMORPH_DESYNCS),
    'alpine',
])
def test_local_alpine_state_survives(page: Page, live_server: LiveServer, strategy: str) -> None:
    open_lab(page, live_server, strategy)
    dirty_the_dom(page)

    apply_and_settle(page)

    expect(role(page, 'alpha', 'details')).to_be_visible()
    expect(role(page, 'alpha', 'counter')).to_have_text('2')
    expect(role(page, 'alpha', 'note')).to_have_value('typed by the user')


@pytest.mark.parametrize('strategy', [
    expected_failure('replace', 'replace rebuilds every node, so Alpine re-runs init()'),
    'idiomorph',
    'alpine',
])
def test_alpine_does_not_reinitialise_preserved_cards(
    page: Page, live_server: LiveServer, strategy: str
) -> None:
    open_lab(page, live_server, strategy)
    inits_before = page.evaluate('window.__cardInits')

    apply_and_settle(page)

    # Four cards mounted initially; a preserving strategy re-runs no init().
    assert page.evaluate('window.__cardInits') == inits_before


# --------------------------------------------------------------------------
# 3. Focus and caret: the thing that makes re-render feel broken while typing
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', [
    expected_failure('replace', 'replace rebuilds the input, losing focus and caret'),
    expected_failure('idiomorph', 'idiomorph loses focus and caret (cause not diagnosed)'),
    'alpine',
])
def test_focus_and_caret_survive(page: Page, live_server: LiveServer, strategy: str) -> None:
    open_lab(page, live_server, strategy)

    note = role(page, 'alpha', 'note')
    note.click()
    note.type('hello world')
    # Put the caret in the middle, where a naive rebuild would lose it.
    page.evaluate(
        '() => { const el = document.querySelector(\'#card-alpha [data-role="note"]\');'
        ' el.setSelectionRange(5, 5); }'
    )

    apply_without_stealing_focus(page)

    focused = page.evaluate(
        '() => document.activeElement?.closest("[data-key]")?.dataset.key'
        ' + ":" + (document.activeElement?.dataset.role || "")'
    )
    assert focused == 'alpha:note'
    assert page.evaluate(
        '() => document.querySelector(\'#card-alpha [data-role="note"]\').selectionStart'
    ) == 5


# --------------------------------------------------------------------------
# 4. Reorder: state must follow the card, not the position
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', [
    expected_failure('replace', 'replace rebuilds every node on reorder'),
    expected_failure(
        'idiomorph',
        'idiomorph relocates nodes exactly, then the relocated card desyncs from Alpine state',
    ),
    expected_failure(
        'alpine',
        "Alpine.morph's keyed lookahead relocates only part of a full reversal",
    ),
])
def test_state_follows_card_across_reorder(
    page: Page, live_server: LiveServer, strategy: str
) -> None:
    open_lab(page, live_server, strategy)
    dirty_the_dom(page)

    apply_and_settle(page, action='reorder')

    sequence = mount_sequence(page)
    keys = [entry.split(':')[0] for entry in sequence]
    assert keys == ['delta', 'charlie', 'bravo', 'alpha']

    # Relocating morph  -> ['delta:4', 'charlie:3', 'bravo:2', 'alpha:1']
    # Positional morph  -> ['delta:1', 'charlie:2', 'bravo:3', 'alpha:4']
    assert sequence == ['delta:4', 'charlie:3', 'bravo:2', 'alpha:1'], (
        f'nodes were repurposed positionally rather than relocated: {sequence}'
    )

    # alpha moved to last position; its local state must have moved with it.
    expect(role(page, 'alpha', 'counter')).to_have_text('2')
    expect(role(page, 'alpha', 'note')).to_have_value('typed by the user')


# --------------------------------------------------------------------------
# 5. Membership change: removing a card must not disturb its siblings
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', [
    expected_failure('replace', REPLACE_REBUILDS),
    expected_failure('idiomorph', IDIOMORPH_DESYNCS),
    'alpine',
])
def test_dropping_a_card_leaves_siblings_intact(
    page: Page, live_server: LiveServer, strategy: str
) -> None:
    open_lab(page, live_server, strategy)
    dirty_the_dom(page)

    apply_and_settle(page, action='drop')

    expect(card(page, 'delta')).to_have_count(0)
    expect(role(page, 'alpha', 'counter')).to_have_text('2')
    expect(role(page, 'alpha', 'note')).to_have_value('typed by the user')


# --------------------------------------------------------------------------
# 6. Third-party-owned DOM: Livewire needed wire:ignore for this
# --------------------------------------------------------------------------

@pytest.mark.parametrize('strategy', STRATEGIES)
def test_unprotected_third_party_dom_is_destroyed(
    page: Page, live_server: LiveServer, strategy: str
) -> None:
    open_lab(page, live_server, strategy)
    expect(role(page, 'charlie', 'third-party-unprotected')).to_have_text('PAINTED-BY-JS')

    apply_and_settle(page)

    # Documents the failure mode: the server render has no such content, so any
    # strategy that rebuilds these nodes wipes what the third-party JS wrote.
    expect(role(page, 'charlie', 'third-party-unprotected')).to_have_text('')


@pytest.mark.parametrize('strategy', ['idiomorph', 'alpine'])
def test_ignore_attribute_protects_third_party_dom(
    page: Page, live_server: LiveServer, strategy: str
) -> None:
    open_lab(page, live_server, strategy)
    expect(role(page, 'charlie', 'third-party-protected')).to_have_text('PAINTED-BY-JS')

    apply_and_settle(page)

    expect(role(page, 'charlie', 'third-party-protected')).to_have_text('PAINTED-BY-JS')

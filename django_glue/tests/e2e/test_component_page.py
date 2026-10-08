from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from test_project.fight.models import Fight

if TYPE_CHECKING:
    from playwright.sync_api import Page
    from limelight.application import Application


pytestmark = [pytest.mark.e2e]


def test_component_as_view_full_page_is_interactive(
    page: Page,
    application: Application,
) -> None:
    page.goto(application.url('gorilla:component_card_page', {'start': 9}))

    card = page.get_by_test_id('counter-card')
    expect(card.get_by_test_id('counter-value')).to_have_text('9')
    card.get_by_role('button', name='Increment').click()
    expect(card.get_by_test_id('counter-value')).to_have_text('10')
    page.evaluate("Glue.from(document.querySelector('[data-testid=counter-card]')).$refresh()")
    expect(card.get_by_test_id('counter-value')).to_have_text('10')
    expect(page.locator('html')).to_have_count(1)


def test_component_formset_child_edits_and_deletes_the_owners_records(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    alpha = seeded_gorillas['alpha']
    Fight.objects.create(name='Alpha vs Gamma', red_corner=alpha, blue_corner=seeded_gorillas['gamma'])

    page.goto(application.url('gorilla:fights_editor', {'gorilla': alpha.pk}))
    page.wait_for_function('window.Glue && window.Alpine')

    editor = page.get_by_test_id('fights-editor')
    rows = editor.locator('.fight-row')
    expect(rows).to_have_count(2)
    expect(rows.nth(0).get_by_label('Fight name')).to_have_value('Alpha vs Beta')
    expect(rows.nth(1).get_by_label('Fight name')).to_have_value('Alpha vs Gamma')

    rows.nth(0).get_by_role('button', name='Remove fight').click()
    expect(rows).to_have_count(1)
    rows.nth(0).get_by_label('Fight name').fill('Alpha vs Gamma II')
    assert alpha.fights_as_red_corner.count() == 2

    editor.get_by_role('button', name='Save fights').click()

    expect(editor.get_by_test_id('fights-result')).to_have_text('{"valid":true}')
    assert list(alpha.fights_as_red_corner.values_list('name', flat=True)) == ['Alpha vs Gamma II']
    # The other gorilla's fight was never in this formset.
    assert Fight.objects.filter(name='Gamma Exhibition').exists()


def test_component_callable_keeps_the_formset_childs_unsaved_changes(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    alpha = seeded_gorillas['alpha']
    Fight.objects.create(name='Alpha vs Gamma', red_corner=alpha, blue_corner=seeded_gorillas['gamma'])

    page.goto(application.url('gorilla:fights_editor', {'gorilla': alpha.pk}))
    page.wait_for_function('window.Glue && window.Alpine')

    editor = page.get_by_test_id('fights-editor')
    rows = editor.locator('.fight-row')
    expect(rows).to_have_count(2)

    rows.nth(0).get_by_role('button', name='Remove fight').click()
    expect(rows).to_have_count(1)
    rows.nth(0).get_by_label('Fight name').fill('Alpha vs Gamma II')
    editor.get_by_role('button', name='Add fight').click()
    expect(rows).to_have_count(2)
    rows.nth(1).get_by_label('Fight name').fill('Alpha Sparring')

    # The callable re-renders the component, which rebuilds its formset child
    # from the saved records.
    editor.get_by_role('button', name='Check fights').click()
    expect(editor.get_by_test_id('fights-checks')).to_have_text('1')

    expect(rows).to_have_count(2)
    expect(rows.nth(0).get_by_label('Fight name')).to_have_value('Alpha vs Gamma II')
    expect(rows.nth(1).get_by_label('Fight name')).to_have_value('Alpha Sparring')

    editor.get_by_role('button', name='Save fights').click()

    expect(editor.get_by_test_id('fights-result')).to_have_text('{"valid":true}')
    assert list(alpha.fights_as_red_corner.order_by('pk').values_list('name', flat=True)) == [
        'Alpha vs Gamma II',
        'Alpha Sparring',
    ]


def test_component_formset_child_creates_a_row_under_its_owner(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    alpha = seeded_gorillas['alpha']
    page.goto(application.url('gorilla:fights_editor', {'gorilla': alpha.pk}))
    page.wait_for_function('window.Glue && window.Alpine')

    editor = page.get_by_test_id('fights-editor')
    rows = editor.locator('.fight-row')
    expect(rows).to_have_count(1)

    editor.get_by_role('button', name='Add fight').click()
    expect(rows).to_have_count(2)
    rows.nth(1).get_by_label('Fight name').fill('Alpha Sparring')
    editor.get_by_role('button', name='Save fights').click()

    expect(editor.get_by_test_id('fights-result')).to_have_text('{"valid":true}')
    fight = Fight.objects.get(name='Alpha Sparring')
    assert (fight.red_corner, fight.blue_corner) == (alpha, alpha)

    rejected = page.evaluate(
        """async () => {
            const fights = Glue.from(document.querySelector('[data-testid=fights-editor]')).fights
            try {
                await fights.append({name: 'Hijack', red_corner: 999})
                return false
            } catch (error) {
                return true
            }
        }"""
    )
    assert rejected
    expect(rows).to_have_count(2)


def test_parent_listener_rerenders_when_a_stamped_child_emits(
    page: Page,
    application: Application,
) -> None:
    page.goto(application.url('gorilla:component_tally', {}))
    summary = page.get_by_test_id('tally-summary')
    expect(summary).to_have_text('Last counted 0, 0 counts')

    receives = []
    page.on(
        'request',
        lambda request: receives.append(request) if '$receive' in (request.post_data or '') else None,
    )
    card = page.get_by_test_id('counter-card').nth(1)
    card.get_by_role('button', name='Increment').click()

    expect(summary).to_have_text('Last counted 5, 1 counts')
    assert len(receives) == 1
    # The tally's re-render keeps the mounted card, so its count survives (ADR 025).
    expect(card.get_by_test_id('counter-value')).to_have_text('6')


def test_a_kept_child_placeholder_parses_in_place_inside_a_table(
    page: Page,
    application: Application,
) -> None:
    page.goto(application.url('gorilla:components', {}))

    parent = page.evaluate('''() => {
        const template = document.createElement('template')
        template.innerHTML = '<table><tbody><template data-glue-keep="p[row]"></template></tbody></table>'
        return template.content.querySelector('[data-glue-keep]').parentElement.tagName
    }''')

    assert parent == 'TBODY'


def test_keyed_component_stamps_use_addressed_state_and_events(
    page: Page,
    application: Application,
) -> None:
    page.goto(application.url('gorilla:components', {}))
    cards = page.get_by_test_id('counter-card')
    expect(cards).to_have_count(2)
    expect(cards.nth(0).get_by_test_id('counter-value')).to_have_text('2')
    expect(cards.nth(1).get_by_test_id('counter-value')).to_have_text('5')

    page.evaluate('''() => {
        window.componentEvents = []
        document.querySelector('[data-testid="counter-card"]').addEventListener(
            'counted', event => window.componentEvents.push(event.detail.value)
        )
    }''')
    cards.nth(0).get_by_role('button', name='Increment').click()

    expect(cards.nth(0).get_by_test_id('counter-value')).to_have_text('3')
    expect(cards.nth(1).get_by_test_id('counter-value')).to_have_text('5')
    assert page.evaluate('window.componentEvents') == [3]
    assert page.evaluate('''() => {
        const card = document.querySelector('[data-testid="counter-card"]')
        const proxy = Glue.from(card.querySelector('button'))
        return proxy && proxy.$el === card && !Glue.component
    }''')

    page.evaluate('''() => {
        const cards = document.querySelectorAll('[data-testid="counter-card"]')
        window.removedCard = Glue.from(cards[0])
        window.keptCard = Glue.from(cards[1])
    }''')
    page.get_by_test_id('dashboard-drop').click()

    expect(cards).to_have_count(1)
    expect(cards.first.get_by_test_id('counter-value')).to_have_text('5')
    assert page.evaluate('''() => {
        const card = document.querySelector('[data-testid="counter-card"]')
        return removedCard._record.disposed && Glue.from(card) === keptCard
    }''')

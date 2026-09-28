from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

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

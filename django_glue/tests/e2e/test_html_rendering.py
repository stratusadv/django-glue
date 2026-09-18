from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer


pytestmark = [pytest.mark.e2e]


@pytest.mark.parametrize('mode', ['inner', 'outer'])
def test_glue_view_preserves_local_state_focus_and_widgets(
    page: Page,
    live_server: LiveServer,
    mode: str,
) -> None:
    page.goto(f'{live_server.url}/lab/morph/')
    page.wait_for_function('window.__cardInits === 4')
    counter = page.locator('#card-alpha [data-role="counter"]')
    page.locator('#card-alpha [data-role="bump"]').click()
    note = page.locator('#card-alpha [data-role="note"]')
    note.fill('hello world')
    page.evaluate('''() => {
        window.heldCard = document.querySelector('#card-alpha')
        window.heldRegion = document.querySelector('#morph-region')
        document.querySelector('#card-alpha input').setSelectionRange(5, 5)
    }''')

    page.evaluate('''async mode => {
        const view = Glue.view('/lab/morph/region/')
        if (mode === 'inner') {
            const post = view.post.bind(view)
            view.post = async () => {
                const template = document.createElement('template')
                template.innerHTML = await post()
                return template.content.firstElementChild.innerHTML
            }
            await view.renderInnerHtml('#morph-region')
        } else {
            await view.renderOuterHtml('#morph-region')
        }
    }''', mode)

    expect(page.locator('#card-alpha [data-role="server-value"]')).to_have_text('alpha-v2')
    expect(counter).to_have_text('1')
    expect(note).to_have_value('hello world')
    expect(note).to_be_focused()
    expect(page.locator('#card-charlie [data-role="third-party-protected"]')).to_have_text('PAINTED-BY-JS')
    expect(page.locator('#card-charlie [data-role="third-party-unprotected"]')).to_have_text('')
    assert page.evaluate('document.querySelector("#card-alpha input").selectionStart') == 5
    assert page.evaluate('window.heldCard === document.querySelector("#card-alpha")')
    assert page.evaluate('window.heldRegion === document.querySelector("#morph-region")')
    assert page.evaluate('window.__cardInits') == 4

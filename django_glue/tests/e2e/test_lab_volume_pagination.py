from __future__ import annotations

import os

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from limelight import DemoSession

from test_project.lab.models import Specimen

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from limelight.application import Application


# pytest-playwright drives Django's live_server test-DB setup from inside its own asyncio event
# loop; without this, Django's SynchronousOnlyOperation guard trips on session-scoped DB setup.
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

pytestmark = [pytest.mark.e2e]

SPECIMEN_COUNT = 60
BATCH_SIZE = 25  # matches the fixed BATCH_SIZE in test_project/lab/views/volume_views.py


@pytest.fixture
def seeded_specimens(transactional_db):
    del transactional_db

    Specimen.objects.all().delete()
    Specimen.seed(SPECIMEN_COUNT)


def real_rows(page: Page):
    # The batched table pads short batches with blank filler rows (`td[colspan]`) to keep the
    # table height stable; exclude those to count only rows that carry real specimen data.
    return page.locator('table tbody tr').filter(has_not=page.locator('td[colspan]'))


def test_batched_table_seeks_through_specimens_demo(
    page: Page,
    application: Application,
    seeded_specimens: None,
) -> None:
    del seeded_specimens

    demo = DemoSession.start(page, application, shot_directory_name='lab-volume-batched-table')
    demo.goto('lab:performance:volume')
    expect(page.get_by_role('heading', name='Test Lab')).to_be_visible()
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Seek Pagination, Batch by Batch',
        kicker='django-glue',
        subtitle=f'{SPECIMEN_COUNT} specimens, {BATCH_SIZE} rows per batch, no OFFSET and no COUNT(*) per click.',
    )

    next_button = page.get_by_role('button', name='Next', exact=True)
    rows = real_rows(page)

    demo.narrate('The first batch seeks from the start of the table', step='1')
    expect(rows).to_have_count(BATCH_SIZE)
    expect(rows.first.locator('td').first).to_have_text('1')
    demo.spotlight(next_button, label='Next')
    expect(next_button).to_be_enabled()

    demo.narrate('Each click seeks forward from the last row seen, not from an offset', step='2')
    demo.click(next_button)
    expect(rows.first.locator('td').first).to_have_text('26')
    expect(rows).to_have_count(BATCH_SIZE)
    expect(next_button).to_be_enabled()

    demo.narrate('The final batch disables Next once seek_batch() reports has_next=False', step='3')
    demo.click(next_button)
    expect(rows.first.locator('td').first).to_have_text('36')
    expect(rows).to_have_count(BATCH_SIZE)
    expect(next_button).to_be_disabled()


def test_infinite_scroll_typeahead_loads_more_on_scroll_demo(
    page: Page,
    application: Application,
    seeded_specimens: None,
) -> None:
    del seeded_specimens

    demo = DemoSession.start(page, application, shot_directory_name='lab-volume-infinite-scroll')
    demo.goto('lab:performance:volume')
    expect(page.get_by_role('heading', name='Test Lab')).to_be_visible()
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Infinite Scroll Without Loading Everything',
        kicker='django-glue',
        subtitle='Scrolling to the sentinel calls loadMore(); count() is a separate call, fetched once.',
    )

    search = page.get_by_placeholder('Search 100,000 specimens')
    dropdown_items = page.locator('.dropdown-menu.show .dropdown-item')
    sentinel = page.locator('.dropdown-menu.show > div.border-top')

    demo.narrate('Opening the dropdown loads the first batch', step='1')
    demo.click(search)
    expect(dropdown_items).to_have_count(BATCH_SIZE)
    demo.spotlight(sentinel, label='Scroll sentinel', scroll=False)

    demo.narrate('Scrolling to the sentinel triggers loadMore(), batch by batch', step='2')
    for _ in range(3):
        if page.get_by_text(f'All {SPECIMEN_COUNT} shown').is_visible():
            break

        sentinel.scroll_into_view_if_needed()
        expect(page.get_by_text('Loading...')).to_be_hidden()

    expect(dropdown_items).to_have_count(SPECIMEN_COUNT)
    # `total` is fetched once via refreshTotal()'s count() call on x-init/search change, never by
    # loadMore() -- the "All N shown" label reaching the true total confirms it landed correctly
    # without needing a COUNT(*) on every scroll-triggered batch.
    expect(page.get_by_text(f'All {SPECIMEN_COUNT} shown')).to_be_visible()

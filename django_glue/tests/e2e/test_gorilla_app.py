from __future__ import annotations

import re

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from limelight import DemoSession

from test_project.gorilla.models import Gorilla

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

    from limelight.application import Application


pytestmark = [pytest.mark.e2e]

# `seeded_gorillas` registers Alpha Atlas / Beta Boulder / Gamma Grove, and the combatants page's
# default `orderBy: 'name'` sorts ascending -- so with no search/order/slice applied, `.card-gorilla`
# is deterministically [Alpha, Beta, Gamma] and no name-matching lookup is needed to find one.
ALPHA_INDEX = 0


def gorilla_card(page: Page, index: int) -> Locator:
    # Scoped to the roster grid specifically: `.card-gorilla` alone also matches the profile
    # card the inner/outer modals render from `detail_page_partial.html`, so once a modal has
    # rendered once, a bare `.card-gorilla` locator can resolve to modal content instead of a
    # roster card.
    return page.locator('.row.g-4 .card-gorilla').nth(index)


def wait_for_no_modal_backdrop(page: Page) -> None:
    page.wait_for_function(
        """() => !document.querySelector('.modal.show') && !document.querySelector('.modal-backdrop')"""
    )


def test_combatants_page_initializes_glue_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-queryset-bootstrap')

    demo.title_card(
        'Glue QuerySet Bootstrap',
        kicker='django-glue',
        subtitle='A Glue.queryset() registration renders as full model glue objects, no page reload.',
    )

    demo.goto('gorilla:list')
    expect(page.get_by_role('heading', name='Gorilla Fight Simulator')).to_be_visible()
    page.wait_for_function('window.Glue && window.Alpine')

    demo.narrate('Three fighters load from one queryset registration', step='1')
    fighter_names = page.get_by_placeholder('Fighter Name')
    expect(fighter_names).to_have_count(3)
    expect(fighter_names.nth(0)).to_have_value('Alpha Atlas')
    expect(fighter_names.nth(1)).to_have_value('Beta Boulder')
    expect(fighter_names.nth(2)).to_have_value('Gamma Grove')
    demo.spotlight(gorilla_card(page, ALPHA_INDEX), label='Fighter card')

    demo.narrate('The client registry mirrors what the server exposed', step='2')
    glue_state = page.evaluate(
        """() => ({
            querySets: Object.keys(window.Glue.querySet),
            models: Object.keys(window.Glue.model),
            hasGlobalMessageHandler: typeof window.Glue._onMessage === 'function'
        })"""
    )
    assert glue_state['querySets'] == ['gorillas']
    assert glue_state['hasGlobalMessageHandler'] is True
    assert glue_state['models'] == ['new_gorilla_model']


def test_queryset_filter_order_slice_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-filter-order-slice')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Chaining filter, orderBy, and slice',
        kicker='django-glue',
        subtitle='Every control on this page maps straight onto GlueQuerySetProxy chain methods.',
    )

    fighter_names = page.get_by_placeholder('Fighter Name')
    search = page.get_by_placeholder('Search fighters by name...')
    demo.narrate('filter() narrows the roster server-side', step='1')
    demo.fill(search, 'Beta')
    # Wait for the count to settle before reading a value -- the debounced filter passes through a
    # transient multi-match state, and to_have_value() on a not-yet-unique locator is a hard strict
    # mode error rather than something its own polling waits out.
    expect(fighter_names).to_have_count(1)
    expect(fighter_names).to_have_value('Beta Boulder')

    demo.narrate('orderBy() re-sorts the same queryset', step='2')
    demo.fill(search, '')
    order_select = page.locator('select.form-select').first
    demo.select(order_select, 'Rank Points (High to Low)')
    first_visible_name = page.get_by_placeholder('Fighter Name').first
    expect(first_visible_name).to_have_value('Gamma Grove')

    demo.narrate('slice() bounds the window without another round trip', step='3')
    demo.fill(page.get_by_placeholder('Start Index'), '1')
    demo.fill(page.get_by_placeholder('Stop Index'), '2')
    page.wait_for_function("""() => document.querySelectorAll('input[placeholder="Fighter Name"]').length < 3""")


def test_many_to_many_choices_load_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-m2m-choices')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Many-to-Many Relations',
        kicker='django-glue',
        subtitle='Each queryset item resolves its own related set and its own choice list.',
    )
    demo.narrate('Every gorilla loads its selected skills and the full skill catalog')

    skill_state = page.evaluate(
        """async () => {
            const gorillas = await window.Glue.querySet.gorillas
                .filter({name__icontains: ''})
                .orderBy('name')
                .slice(0, 100)
                .all();
            return Promise.all(gorillas.items.map(async gorilla => {
                const skills = await gorilla.skills.all();
                const choices = await gorilla.foreign_key_choices({field_name: 'skills'});
                return {
                    name: String(gorilla.name),
                    selected: skills.items.map(skill => String(skill.name)),
                    choiceCount: choices.length,
                };
            }));
        }"""
    )

    assert skill_state == [
        {'name': 'Alpha Atlas', 'selected': ['Chest Pound', 'Jungle Roar'], 'choiceCount': 2},
        {'name': 'Beta Boulder', 'selected': ['Chest Pound'], 'choiceCount': 2},
        {'name': 'Gamma Grove', 'selected': [], 'choiceCount': 2},
    ]


def test_fight_page_hydrates_fields_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='fight-relation-choice-fields')
    demo.goto('fight:list')
    expect(page.get_by_role('heading', name='Gorilla Fight Simulator')).to_be_visible()
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Foreign Keys and Choice Fields',
        kicker='django-glue',
        subtitle='A ForeignKey field and a choices= CharField both hydrate as selectable, labeled fields.',
    )
    demo.narrate('Corners resolve to gorillas; location/weather/terrain/status resolve to their labels')

    fight_state = page.evaluate(
        """async () => {
            const fights = await window.Glue.querySet.fights
                .filter({name__icontains: ''})
                .orderBy('name')
                .all();
            const fight = fights.items[0];
            const fields = fight.$fields;
            await Promise.all([fields.red_corner_id.ensureChoices(), fields.blue_corner_id.ensureChoices()]);
            return {
                name: String(fight.name),
                cornerChoices: [fields.red_corner_id.choices.length, fields.blue_corner_id.choices.length],
                choiceCounts: [
                    fields.location.choices.length > 0,
                    fields.weather_conditions.choices.length > 0,
                    fields.terrain_type.choices.length > 0,
                    fields.status.choices.length > 0,
                ],
                redCorner: fields.red_corner_id.selectedChoice?.label,
                blueCorner: fields.blue_corner_id.selectedChoice?.label,
                location: fields.location.selectedChoice?.label,
                weather: fields.weather_conditions.selectedChoice?.label,
                terrain: fields.terrain_type.selectedChoice?.label,
                status: fields.status.selectedChoice?.label,
            };
        }"""
    )

    assert fight_state == {
        'name': 'Alpha vs Beta',
        'cornerChoices': [3, 3],
        'choiceCounts': [True, True, True, True],
        'redCorner': 'Alpha Atlas',
        'blueCorner': 'Beta Boulder',
        'location': 'Thunderdome',
        'weather': 'Ominous Clouds',
        'terrain': 'Lava Floor',
        'status': 'In Progress',
    }


def test_model_edit_save_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-model-edit-save')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Editing and Saving a Model Proxy',
        kicker='django-glue',
        subtitle='gorilla.save() writes straight back to the Django model instance.',
    )

    card = gorilla_card(page, ALPHA_INDEX)
    backstory = card.get_by_placeholder('Fighter backstory...')
    age = card.get_by_role('spinbutton').nth(0)
    save_button = card.get_by_role('button', name='Save')

    demo.narrate('Edit two fields on the client', step='1')
    demo.fill(backstory, 'Updated by Playwright e2e.')
    demo.fill(age, '13')

    demo.narrate('save() persists the whole diff in one call', step='2')
    demo.click(save_button)

    expect(page.get_by_role('alert')).to_contain_text('Fighter saved successfully!')
    assert Gorilla.objects.get(name='Alpha Atlas').description == 'Updated by Playwright e2e.'
    assert Gorilla.objects.get(name='Alpha Atlas').age == 13


def test_global_message_handler_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-global-message-handler')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Server-Pushed Messages',
        kicker='django-glue',
        subtitle="A bound attribute's response can carry messages the global handler renders as a toast.",
    )

    card = gorilla_card(page, ALPHA_INDEX)
    speak_button = card.get_by_role('button', name='Speak')
    demo.narrate('battle_cry() returns a message alongside its result')
    demo.spotlight(speak_button, label='Speak')
    demo.click(speak_button)

    expect(page.get_by_role('alert')).to_contain_text('Alpha Atlas beats their chest!')
    expect(page.get_by_role('alert')).to_contain_text('triggered by')


def test_proxy_message_handler_override_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-proxy-message-handler-override')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Overriding the Message Handler Per Proxy',
        kicker='django-glue',
        subtitle='gorilla.onMessage() intercepts messages for one proxy instead of the global handler.',
    )

    card = gorilla_card(page, ALPHA_INDEX)
    demo.narrate('Opt this fighter into a local handler', step='1')
    demo.check(card.get_by_label('Use local message handler'))

    demo.narrate('The same server call now renders locally, not globally', step='2')
    demo.click(card.get_by_role('button', name='Speak'))

    expect(page.get_by_role('alert')).to_contain_text('From Local Message Handler:')
    expect(page.get_by_role('alert')).to_contain_text('Alpha Atlas beats their chest!')


def test_inner_profile_modal_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-inner-profile-modal')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Glue.view() Rendering Inner HTML',
        kicker='django-glue',
        subtitle='renderInnerHtml() fills an existing modal body with a server-rendered fragment.',
    )

    profile_button = gorilla_card(page, ALPHA_INDEX).get_by_role('button', name='Profile (Inner)')
    demo.narrate('Open the fighter profile')
    demo.click(profile_button)

    modal = page.locator('#profileModal')
    expect(modal).to_have_class(re.compile(r'\bshow\b'))
    expect(modal.get_by_placeholder('Fighter Name')).to_have_value('Alpha Atlas')
    expect(modal.locator('.stat-value')).to_contain_text(['700', '12', '210.5', '1.8'])
    demo.spotlight(modal, label='Registered as window.Glue.model.gorilla', scroll=False)
    assert page.evaluate('() => window.Glue.model.gorilla?.name') == 'Alpha Atlas'


def test_outer_profile_modal_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-outer-profile-modal')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Glue.view() Rendering Outer HTML',
        kicker='django-glue',
        subtitle='renderOuterHtml() replaces the whole placeholder, so the modal can be reopened repeatedly.',
    )

    for attempt in range(2):
        demo.narrate(f'Open and close the outer-HTML modal (pass {attempt + 1})')
        card = gorilla_card(page, ALPHA_INDEX)
        card.get_by_role('button', name='Profile (Outer)').click()

        modal = page.locator('#profileModalOuter')
        expect(modal).to_have_class(re.compile(r'\bshow\b'))
        expect(modal.locator('.modal-body')).to_be_visible()
        expect(modal.get_by_placeholder('Fighter Name')).to_have_value('Alpha Atlas')

        modal.locator('.btn-close').click()
        expect(modal).not_to_have_class(re.compile(r'\bshow\b'))
        wait_for_no_modal_backdrop(page)


def test_create_model_modal_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-create-model-modal')
    demo.goto('gorilla:list')
    page.wait_for_function('window.Glue && window.Alpine')

    demo.title_card(
        'Creating Through a Model Proxy',
        kicker='django-glue',
        subtitle='Glue.model.new_gorilla_model.save() creates a row and the queryset refreshes to show it.',
    )

    demo.narrate('Open the model-proxy add form', step='1')
    add_button = page.get_by_role('button', name='+ Add via Model')
    demo.spotlight(add_button, label='Add via Model')
    demo.click(add_button)

    modal = page.locator('#addGorillaModelModal')
    expect(modal).to_have_class(re.compile(r'\bshow\b'))

    demo.narrate('Fill in the new fighter', step='2')
    demo.fill(modal.locator('input').nth(0), 'Delta Drummer')
    demo.fill(modal.locator('textarea').first, 'Created through the model proxy modal.')
    demo.fill(modal.locator('input').nth(1), '18')
    demo.fill(modal.locator('input').nth(2), '240')
    demo.fill(modal.locator('input').nth(3), '1.9')
    demo.fill(modal.locator('input').nth(4), '0')
    demo.click(modal.get_by_role('button', name='Create Fighter'))

    expect(page.get_by_role('alert')).to_contain_text('Fighter created successfully!')
    expect(modal).not_to_have_class(re.compile(r'\bshow\b'))
    wait_for_no_modal_backdrop(page)

    demo.narrate('The roster refreshes without a page reload', step='3')
    fighter_names = page.get_by_placeholder('Fighter Name')
    demo.fill(page.get_by_placeholder('Search fighters by name...'), 'Delta')
    expect(fighter_names).to_have_count(1)
    expect(fighter_names).to_have_value('Delta Drummer')
    assert Gorilla.objects.filter(name='Delta Drummer').exists()


def test_progressive_form_demo(
    page: Page,
    application: Application,
    seeded_gorillas: dict,
) -> None:
    del seeded_gorillas

    demo = DemoSession.start(page, application, shot_directory_name='gorilla-progressive-form')
    demo.goto('gorilla:progressive_form')
    expect(page.get_by_role('heading', name='Build a Gorilla')).to_be_visible()

    demo.title_card(
        'A Multi-Step Progressive Form',
        kicker='django-glue',
        subtitle='Each step validates server-side before advancing; state accumulates across steps.',
    )

    demo.narrate('Step 1 rejects an empty submission', step='1')
    demo.click(page.get_by_role('button', name='Next Step'))
    expect(page.get_by_text('Please fix the errors above.')).to_be_visible()

    demo.fill(page.get_by_placeholder("Enter the fighter's name"), 'Echo Ember')
    demo.fill(page.get_by_placeholder('Enter age'), '9')
    demo.click(page.get_by_role('button', name='Next Step'))
    expect(page.get_by_text('Step 2: Physical Attributes')).to_be_visible()

    demo.narrate('Step 2 collects physical attributes', step='2')
    demo.fill(page.get_by_placeholder('Enter weight'), '199')
    demo.fill(page.get_by_placeholder('Enter height'), '1.6')
    demo.click(page.get_by_role('button', name='Next Step'))
    expect(page.get_by_text('Step 3: Final Details')).to_be_visible()

    demo.narrate('Step 3 submits the accumulated state as one fighter', step='3')
    demo.fill(
        page.get_by_placeholder("Enter the fighter's backstory, achievements, and fighting spirit..."),
        'Created by the progressive form e2e flow.',
    )
    demo.click(page.get_by_role('button', name='Create Fighter'))

    expect(page.get_by_text('Fighter Created!')).to_be_visible()
    expect(page.get_by_text('Fighter "Echo Ember" created!')).to_be_visible()
    assert Gorilla.objects.filter(name='Echo Ember').exists()

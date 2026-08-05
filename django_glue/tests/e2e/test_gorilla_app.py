from __future__ import annotations

import re
import os
import unittest
from contextlib import suppress

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

from test_project.fight.choices import (
    FightStatusChoices,
    LocationChoices,
    TerrainTypeChoices,
    WeatherConditionChoices,
)
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill


os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@unittest.skipUnless(
    os.environ.get('DJANGO_GLUE_RUN_E2E') == '1',
    'Playwright e2e tests are opt-in. Use `just test-e2e`.',
)
class GorillaAppE2ETestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        try:
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            with suppress(Exception):
                cls._playwright.stop()
            pytest.skip(
                'Playwright Chromium is not installed. Run `.venv/Scripts/python.exe -m playwright install chromium`.',
                allow_module_level=True,
            )

    @classmethod
    def tearDownClass(cls) -> None:
        with suppress(Exception):
            cls._browser.close()
        with suppress(Exception):
            cls._playwright.stop()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self._seed_data()
        self.context = self._browser.new_context(viewport={'width': 1280, 'height': 900})
        self.page = self.context.new_page()
        self.console_errors: list[str] = []
        self.page.on('console', self._capture_console)
        self.page.on('pageerror', lambda exc: self.console_errors.append(str(exc)))

    def tearDown(self) -> None:
        with suppress(Exception):
            self.context.close()
        super().tearDown()

    @classmethod
    def _seed_data(cls) -> None:
        Fight.objects.all().delete()
        Skill.objects.all().delete()
        Gorilla.objects.all().delete()

        chest_pound = Skill.objects.create(
            name='Chest Pound',
            description='A confident display.',
            difficulty=2,
            level=30,
        )
        jungle_roar = Skill.objects.create(
            name='Jungle Roar',
            description='A room-shaking roar.',
            difficulty=5,
            level=45,
        )

        alpha = Gorilla.objects.create(
            name='Alpha Atlas',
            description='Steady leader of the troop.',
            age=12,
            weight=210.5,
            height=1.8,
            rank_points=700,
        )
        alpha.skills.set([chest_pound, jungle_roar])

        beta = Gorilla.objects.create(
            name='Beta Boulder',
            description='Heavy hitter with careful footwork.',
            age=24,
            weight=315.0,
            height=1.65,
            rank_points=300,
        )
        beta.skills.set([chest_pound])

        gamma = Gorilla.objects.create(
            name='Gamma Grove',
            description='Fast climber from the canopy.',
            age=8,
            weight=155.5,
            height=1.4,
            rank_points=950,
        )

        Fight.objects.create(
            name='Alpha vs Beta',
            description='A deterministic e2e fight.',
            red_corner=alpha,
            blue_corner=beta,
            location=LocationChoices.THUNDERDOME,
            weather_conditions=WeatherConditionChoices.OMINOUS_CLOUDS,
            terrain_type=TerrainTypeChoices.LAVA_FLOOR,
            status=FightStatusChoices.IN_PROGRESS,
            spectator_count=1234,
        )

        Fight.objects.create(
            name='Gamma Exhibition',
            description='A second fight for filtering.',
            red_corner=gamma,
            blue_corner=alpha,
            location=LocationChoices.COLOSSEUM,
            weather_conditions=WeatherConditionChoices.PERFECT_BLUE_SKY,
            terrain_type=TerrainTypeChoices.STEEL_DEATH_CAGE,
            status=FightStatusChoices.SCHEDULED,
            spectator_count=50,
        )

    def _capture_console(self, message) -> None:
        if message.type == 'error' and 'favicon.ico' not in message.text:
            self.console_errors.append(message.text)

    def _assert_no_console_errors(self) -> None:
        assert self.console_errors == []

    def _goto_combatants(self) -> None:
        self.page.goto(self.live_server_url)
        expect(self.page.get_by_role('heading', name='Gorilla Fight Simulator')).to_be_visible()
        self.page.wait_for_function('window.Glue && window.Alpine')

    def _goto_fights(self) -> None:
        self.page.goto(f'{self.live_server_url}/fight/')
        expect(self.page.get_by_role('heading', name='Gorilla Fight Simulator')).to_be_visible()
        self.page.wait_for_function('window.Glue && window.Alpine')

    def _wait_for_no_modal_backdrop(self) -> None:
        self.page.wait_for_function(
            """() => !document.querySelector('.modal.show') && !document.querySelector('.modal-backdrop')"""
        )

    def _fighter_card(self, name: str):
        card_id = self.page.evaluate(
            """name => {
                const input = Array.from(document.querySelectorAll('input[placeholder="Fighter Name"]'))
                    .find(input => input.value === name);
                const card = input?.closest('.card-gorilla');
                if (!card) {
                    return null;
                }
                const id = `fighter-card-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
                card.dataset.e2eFighterCard = id;
                return id;
            }""",
            name,
        )
        assert card_id, f'Could not find fighter card for {name!r}'
        return self.page.locator(f'[data-e2e-fighter-card="{card_id}"]')

    def _fighter_name_input(self, name: str):
        index = self._fighter_index(name)
        return self.page.locator('input[placeholder="Fighter Name"]').nth(index)

    def _fighter_index(self, name: str) -> int:
        index = self.page.evaluate(
            """name => Array.from(document.querySelectorAll('input[placeholder="Fighter Name"]'))
                .findIndex(input => input.value === name)""",
            name,
        )
        assert index >= 0, f'Could not find fighter card for {name!r}'
        return index

    def test_combatants_page_initializes_glue_and_renders_queryset(self) -> None:
        self._goto_combatants()

        expect(self._fighter_name_input('Alpha Atlas')).to_be_visible()
        expect(self._fighter_name_input('Beta Boulder')).to_be_visible()
        expect(self._fighter_name_input('Gamma Grove')).to_be_visible()

        glue_state = self.page.evaluate(
            """() => ({
                querySets: Object.keys(window.Glue.querySet),
                models: Object.keys(window.Glue.model),
                hasGlobalMessageHandler: typeof window.Glue._onMessage === 'function'
            })"""
        )

        assert glue_state['querySets'] == ['gorillas']
        assert glue_state['hasGlobalMessageHandler'] is True
        assert any(name.startswith('gorillas__') for name in glue_state['models'])
        self._assert_no_console_errors()

    def test_queryset_controls_update_visible_cards(self) -> None:
        self._goto_combatants()

        self.page.get_by_placeholder('Search fighters by name...').fill('Beta')
        expect(self._fighter_name_input('Beta Boulder')).to_be_visible()
        expect(self.page.locator('input[placeholder="Fighter Name"]')).to_have_count(1)

        self.page.get_by_placeholder('Search fighters by name...').fill('')
        self.page.locator('select.form-select').first.select_option('-rank_points')
        first_visible_name = self.page.locator('input[placeholder="Fighter Name"]').first
        expect(first_visible_name).to_have_value('Gamma Grove')

        self.page.get_by_placeholder('Start Index').fill('1')
        self.page.get_by_placeholder('Stop Index').fill('2')
        self.page.wait_for_function(
            """() => document.querySelectorAll('input[placeholder="Fighter Name"]').length < 3"""
        )
        self._assert_no_console_errors()

    def test_many_to_many_relation_choices_load_for_each_queryset_item(self) -> None:
        self._goto_combatants()

        self.page.wait_for_function(
            """() => {
                const gorillas = window.Glue?.querySet?.gorillas?.queryWithParams({
                    filter: {name__icontains: ''},
                    slice: {start: 0, stop: 100},
                    order_by: 'name',
                }) || [];
                return gorillas.length === 3
                    && gorillas.every(gorilla => Array.isArray(gorilla.skills.choices))
                    && gorillas.every(gorilla => gorilla.skills.choices.length === 2);
            }"""
        )

        skill_state = self.page.evaluate(
            """() => window.Glue.querySet.gorillas.queryWithParams({
                filter: {name__icontains: ''},
                slice: {start: 0, stop: 100},
                order_by: 'name',
            }).map(gorilla => ({
                name: String(gorilla.name),
                selected: gorilla.skills.selectedChoices.map(choice => choice.label),
                choiceCount: gorilla.skills.choices.length,
            }))"""
        )

        assert skill_state == [
            {'name': 'Alpha Atlas', 'selected': ['Chest Pound', 'Jungle Roar'], 'choiceCount': 2},
            {'name': 'Beta Boulder', 'selected': ['Chest Pound'], 'choiceCount': 2},
            {'name': 'Gamma Grove', 'selected': [], 'choiceCount': 2},
        ]
        self._assert_no_console_errors()

    def test_fight_page_hydrates_relation_and_choice_fields(self) -> None:
        self._goto_fights()

        self.page.wait_for_function(
            """() => {
                const fight = window.Glue?.querySet?.fights?.queryWithParams({
                    filter: {name__icontains: ''}
                })?.[0];
                return fight
                    && fight.red_corner.choices.length === 3
                    && fight.blue_corner.choices.length === 3
                    && fight.location.choices.length > 0
                    && fight.weather_conditions.choices.length > 0
                    && fight.terrain_type.choices.length > 0
                    && fight.status.choices.length > 0;
            }"""
        )

        fight_state = self.page.evaluate(
            """() => {
                const fight = window.Glue.querySet.fights.queryWithParams({
                    filter: {name__icontains: ''}
                })[0];
                return {
                    name: String(fight.name),
                    redCorner: fight.red_corner.selectedChoice?.label,
                    blueCorner: fight.blue_corner.selectedChoice?.label,
                    location: fight.location.selectedChoice?.label,
                    weather: fight.weather_conditions.selectedChoice?.label,
                    terrain: fight.terrain_type.selectedChoice?.label,
                    status: fight.status.selectedChoice?.label,
                };
            }"""
        )

        assert fight_state == {
            'name': 'Alpha vs Beta',
            'redCorner': 'Alpha Atlas',
            'blueCorner': 'Beta Boulder',
            'location': 'Thunderdome',
            'weather': 'Ominous Clouds',
            'terrain': 'Lava Floor',
            'status': 'In Progress',
        }
        self._assert_no_console_errors()

    def test_model_field_edit_save_persists_to_database(self) -> None:
        self._goto_combatants()

        card = self._fighter_card('Alpha Atlas')
        card.get_by_placeholder('Fighter backstory...').fill('Updated by Playwright e2e.')
        card.get_by_role('spinbutton').nth(0).fill('13')
        card.get_by_role('button', name='Save').click()

        expect(self.page.get_by_role('alert')).to_contain_text('Fighter saved successfully!')
        self.assertEqual(Gorilla.objects.get(name='Alpha Atlas').description, 'Updated by Playwright e2e.')
        self.assertEqual(Gorilla.objects.get(name='Alpha Atlas').age, 13)
        self._assert_no_console_errors()

    def test_global_message_handler_displays_battle_cry_notification(self) -> None:
        self._goto_combatants()

        card = self._fighter_card('Alpha Atlas')
        card.get_by_role('button', name='Speak').click()

        expect(self.page.get_by_role('alert')).to_contain_text('Alpha Atlas beats their chest!')
        expect(self.page.get_by_role('alert')).to_contain_text('triggered by')
        self._assert_no_console_errors()

    def test_proxy_message_handler_override_displays_local_notification(self) -> None:
        self._goto_combatants()

        card = self._fighter_card('Alpha Atlas')
        card.get_by_label('Use local message handler').check()
        card.get_by_role('button', name='Speak').click()

        expect(self.page.get_by_role('alert')).to_contain_text('From Local Message Handler:')
        expect(self.page.get_by_role('alert')).to_contain_text('Alpha Atlas beats their chest!')
        self._assert_no_console_errors()

    def test_glue_view_inner_profile_modal_renders_registered_proxy(self) -> None:
        self._goto_combatants()

        self._fighter_card('Alpha Atlas').get_by_role('button', name='Profile (Inner)').click()

        modal = self.page.locator('#profileModal')
        expect(modal).to_have_class(re.compile(r'\bshow\b'))
        expect(modal.get_by_placeholder('Fighter Name')).to_have_value('Alpha Atlas')
        expect(modal.locator('.stat-value')).to_contain_text(['700', '12', '210.5', '1.8'])
        assert self.page.evaluate('() => window.Glue.model.gorilla?.name') == 'Alpha Atlas'
        self._assert_no_console_errors()

    def test_glue_view_outer_profile_modal_renders_repeatedly(self) -> None:
        self._goto_combatants()

        for _ in range(2):
            card = self._fighter_card('Alpha Atlas')
            card.locator('button').filter(has_text='Profile (Outer)').click()
            modal = self.page.locator('#profileModalOuter')
            expect(modal).to_have_class(re.compile(r'\bshow\b'))
            expect(modal.locator('.modal-body')).to_be_visible()
            expect(modal.get_by_placeholder('Fighter Name')).to_have_value('Alpha Atlas')
            modal.locator('.btn-close').click()
            expect(modal).not_to_have_class(re.compile(r'\bshow\b'))
            self._wait_for_no_modal_backdrop()

        self._assert_no_console_errors()

    def test_create_model_modal_creates_fighter_and_refreshes_queryset(self) -> None:
        self._goto_combatants()

        self.page.get_by_role('button', name='+ Add via Model').click()
        modal = self.page.locator('#addGorillaModelModal')
        expect(modal).to_have_class(re.compile(r'\bshow\b'))

        modal.locator('input').nth(0).fill('Delta Drummer')
        modal.locator('textarea').first.fill('Created through the model proxy modal.')
        modal.locator('input').nth(1).fill('18')
        modal.locator('input').nth(2).fill('240')
        modal.locator('input').nth(3).fill('1.9')
        modal.locator('input').nth(4).fill('0')
        modal.get_by_role('button', name='Create Fighter').click()

        expect(self.page.get_by_role('alert')).to_contain_text('Fighter created successfully!')
        expect(modal).not_to_have_class(re.compile(r'\bshow\b'))
        self._wait_for_no_modal_backdrop()
        self.page.get_by_placeholder('Search fighters by name...').fill('Delta')
        self.page.wait_for_function(
            """() => Array.from(document.querySelectorAll('input[placeholder="Fighter Name"]'))
                .some(input => input.value === 'Delta Drummer')"""
        )
        expect(self._fighter_name_input('Delta Drummer')).to_be_visible()
        self.assertTrue(Gorilla.objects.filter(name='Delta Drummer').exists())
        self._assert_no_console_errors()

    def test_progressive_form_validates_steps_and_creates_fighter(self) -> None:
        self.page.goto(f'{self.live_server_url}/progressive_form/')
        expect(self.page.get_by_role('heading', name='Build a Gorilla')).to_be_visible()

        self.page.get_by_role('button', name='Next Step').click()
        expect(self.page.get_by_text('Please fix the errors above.')).to_be_visible()

        self.page.get_by_placeholder("Enter the fighter's name").fill('Echo Ember')
        self.page.get_by_placeholder('Enter age').fill('9')
        self.page.get_by_role('button', name='Next Step').click()
        expect(self.page.get_by_text('Physical attributes validated!')).not_to_be_visible()
        expect(self.page.get_by_text('Step 2: Physical Attributes')).to_be_visible()

        self.page.get_by_placeholder('Enter weight').fill('199')
        self.page.get_by_placeholder('Enter height').fill('1.6')
        self.page.get_by_role('button', name='Next Step').click()
        expect(self.page.get_by_text('Step 3: Final Details')).to_be_visible()

        self.page.get_by_placeholder("Enter the fighter's backstory, achievements, and fighting spirit...").fill(
            'Created by the progressive form e2e flow.'
        )
        self.page.get_by_role('button', name='Create Fighter').click()

        expect(self.page.get_by_text('Fighter Created!')).to_be_visible()
        expect(self.page.get_by_text('Fighter "Echo Ember" created!')).to_be_visible()
        self.assertTrue(Gorilla.objects.filter(name='Echo Ember').exists())
        self._assert_no_console_errors()

from django.test import TestCase
from django.urls import reverse

from test_project.lab.benchmarks import DeckCall
from test_project.lab.models import Specimen
from test_project.lab.views.performance_views import Scenario

SPECIMEN_COUNT = 60
BATCH_SIZE = 25


class SpeedViewTestCase(TestCase):
    def setUp(self):
        Specimen.seed(SPECIMEN_COUNT)

    def run_scenario(self, scenario: Scenario, **params):
        return self.client.get(
            reverse('lab:performance:speed'),
            {'scenario': scenario, 'repeats': 1, **params},
        )

    def test_speed_page_describes_every_scenario_without_running_one(self):
        response = self.client.get(reverse('lab:performance:speed'))

        self.assertEqual(response.status_code, 200)
        for scenario in Scenario:
            self.assertContains(response, f'data-scenario="{scenario}"')
            # Each scenario's result sits in the context under its own name.
            self.assertNotIn(scenario, response.context)

    def test_page_load_measures_each_object_kind(self):
        response = self.run_scenario(Scenario.PAGE_LOAD, count=3)

        kinds = [kind for kind, _measurement in response.context['page_load']]
        self.assertEqual(kinds, ['model', 'queryset', 'form'])
        for _kind, measurement in response.context['page_load']:
            self.assertEqual(measurement.entries, 3)
            self.assertGreater(measurement.payload.tokens, 0)

    def test_batch_answers_one_batch_of_rows(self):
        response = self.run_scenario(Scenario.BATCH, batch_size=BATCH_SIZE)

        # The queryset's own entry, then one entry per row.
        self.assertEqual(response.context['batch'].entries, BATCH_SIZE + 1)

    def test_related_batch_answers_one_batch_of_rows(self):
        response = self.run_scenario(Scenario.RELATED_BATCH, batch_size=BATCH_SIZE)

        self.assertEqual(response.context['related_batch'].entries, BATCH_SIZE + 1)

    def test_scroll_stops_after_the_last_batch(self):
        response = self.run_scenario(Scenario.SCROLL, batch_size=BATCH_SIZE, batches=10)

        steps = response.context['scroll']
        self.assertEqual([step.batch for step in steps], [1, 2, 3])
        self.assertEqual([step.error for step in steps], ['', '', ''])

    def test_component_page_sends_each_entry_twice(self):
        response = self.run_scenario(Scenario.COMPONENT_PAGE, cards=4)

        # A deck and its four cards, each stamped into its root and listed in the init script.
        self.assertEqual(response.context['component_page'].entries, 10)

    def test_component_tree_measures_one_row_per_depth(self):
        response = self.run_scenario(Scenario.COMPONENT_TREE, depth=3, fanout=2)

        components = [components for components, _measurement in response.context['component_tree']]
        self.assertEqual(components, [3, 7, 15])

    def test_component_call_measures_each_deck_call(self):
        response = self.run_scenario(Scenario.COMPONENT_CALL, cards=4)

        calls = [call for call, _measurement in response.context['component_call']]
        self.assertEqual(calls, list(DeckCall))
        for _call, measurement in response.context['component_call']:
            self.assertGreaterEqual(measurement.entries, 1)

    def test_parameters_are_held_within_their_bounds(self):
        response = self.client.get(
            reverse('lab:performance:speed'),
            {'count': 0, 'repeats': 'many', 'batch_size': 10_000},
        )

        self.assertEqual(response.context['count'], 1)
        self.assertEqual(response.context['repeats'], 5)
        self.assertEqual(response.context['batch_size'], 500)

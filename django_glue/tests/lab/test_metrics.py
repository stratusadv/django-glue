import json

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from test_project.lab.benchmarks import page_entries
from test_project.lab.metrics import Metric
from test_project.lab.models import Specimen


def server_timing(response: HttpResponse) -> dict[str, dict[str, str]]:
    """The ``Server-Timing`` header as {name: {'dur': ..., 'desc': ...}}."""
    metrics = {}
    for metric in response['Server-Timing'].split(', '):
        name, *parameters = metric.split(';')
        metrics[name] = dict(parameter.split('=', 1) for parameter in parameters)
    return metrics


@override_settings(DEBUG=True)
class GlueMetricsDebugTestCase(TestCase):
    def setUp(self):
        Specimen.seed(30)

    def call(self, entries: list[dict], attribute: str, kwargs: dict) -> HttpResponse:
        return self.client.post(
            reverse('__dg__:callable_attribute'),
            {'objects': json.dumps([
                {
                    'address': entry['address'],
                    'policy_token': entry['policy_token'],
                    'call': {'attribute': attribute, 'kwargs': kwargs},
                }
                for entry in entries
            ])},
        )

    def specimens_entry(self) -> dict:
        html = self.client.get(reverse('lab:performance:volume')).content.decode()
        return page_entries(html)[0][0]

    def test_page_reports_its_time_queries_and_glue_payload(self):
        response = self.client.get(reverse('lab:performance:volume'))

        metrics = server_timing(response)
        self.assertGreater(float(metrics[Metric.SERVER]['dur']), 0)
        self.assertIn(Metric.QUERIES, metrics)
        self.assertEqual(metrics[Metric.ENTRIES]['dur'], '1')
        self.assertGreater(int(metrics[Metric.TOKENS]['dur']), 0)

    def test_page_gets_the_panel_first_in_its_head(self):
        html = self.client.get(reverse('lab:performance:volume')).content.decode()

        head = html[html.index('<head'):html.index('</head>')]
        self.assertIn('glue-metric-names', head)
        self.assertLess(html.index('glue-metric-names'), html.index('django_glue.js'))

    def test_call_reports_what_was_called_and_its_payload(self):
        response = self.call([self.specimens_entry()], 'query_with_params', {})

        metrics = server_timing(response)
        self.assertEqual(metrics[Metric.CALLS]['desc'], '"specimens.query_with_params"')
        self.assertEqual(metrics[Metric.ENTRIES]['dur'], '26')
        self.assertNotIn(Metric.ERRORS, metrics)

    def test_call_reports_the_error_codes_of_failed_entries(self):
        entry = self.specimens_entry()
        self.client.session.flush()
        self.client.cookies.clear()

        response = self.call([entry], 'query_with_params', {})

        self.assertIn(Metric.ERRORS, server_timing(response))

    def test_a_batch_waking_many_components_is_labelled_by_count(self):
        html = self.client.get(
            reverse('lab:performance:stress'),
            {'cards': 2, 'tallies': 3, 'depth': 1, 'fanout': 1},
        ).content.decode()
        # Each entry rides twice on a page; one per address.
        tallies = {
            entry['address']: entry
            for entry in page_entries(html)[0]
            if entry['address'].startswith('lab_tally')
        }

        response = self.call(list(tallies.values()), 'render', {})

        self.assertEqual(server_timing(response)[Metric.CALLS]['desc'], '"lab_tally.render x3"')


class GlueMetricsOffTestCase(TestCase):
    def test_nothing_is_added_while_debug_is_off(self):
        response = self.client.get(reverse('lab:performance:volume'))

        self.assertFalse(response.has_header('Server-Timing'))
        self.assertNotContains(response, 'glue-metric-names')

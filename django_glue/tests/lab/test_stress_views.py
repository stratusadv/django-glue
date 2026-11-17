from django.test import TestCase
from django.urls import reverse

from test_project.lab.benchmarks import page_entries


class StressViewTestCase(TestCase):
    def test_stress_page_mounts_the_requested_components(self):
        response = self.client.get(
            reverse('lab:performance:stress'),
            {'cards': 3, 'tallies': 2, 'depth': 2, 'fanout': 2},
        )

        self.assertEqual(response.status_code, 200)
        addresses = {entry['address'] for entry in page_entries(response.content.decode())[0]}
        # A deck with 3 cards, 2 tallies, and a tree of 1 + 2 + 4 nodes.
        self.assertEqual(len(addresses), 4 + 2 + 7)

    def test_stress_page_sizes_are_held_within_their_bounds(self):
        response = self.client.get(
            reverse('lab:performance:stress'),
            {'cards': 10_000, 'depth': 99},
        )

        self.assertEqual(response.context['cards'], 500)
        self.assertEqual(response.context['depth'], 5)

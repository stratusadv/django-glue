from django.test import TestCase
from django.urls import reverse

from test_project.lab.models import SPECIES, Specimen


class SpecimenSeedTestCase(TestCase):
    def test_seed_creates_deterministic_rows_with_unique_catalogue_numbers(self):
        created = Specimen.seed(50)

        self.assertEqual(created, 50)
        self.assertEqual(Specimen.objects.count(), 50)
        self.assertEqual(Specimen.objects.first().catalogue_number, 1)
        self.assertEqual(Specimen.objects.last().catalogue_number, 50)
        self.assertTrue(set(Specimen.objects.values_list('species', flat=True)) <= set(SPECIES))

    def test_seed_continues_after_existing_rows(self):
        Specimen.seed(10)
        Specimen.seed(10)

        self.assertEqual(Specimen.objects.count(), 20)
        self.assertEqual(Specimen.objects.last().catalogue_number, 20)


class VolumeViewTestCase(TestCase):
    def test_volume_page_registers_paged_queryset(self):
        Specimen.seed(30)

        response = self.client.get(reverse('lab:performance:volume'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['specimen_count'], 30)
        self.assertContains(response, 'batch_size=25')

    def test_seed_view_creates_rows_and_redirects(self):
        response = self.client.post(reverse('lab:performance:volume_seed'), {'count': 40})

        self.assertRedirects(response, reverse('lab:performance:volume'))
        self.assertEqual(Specimen.objects.count(), 40)

    def test_clear_view_deletes_rows_and_redirects(self):
        Specimen.seed(5)

        response = self.client.post(reverse('lab:performance:volume_clear'))

        self.assertRedirects(response, reverse('lab:performance:volume'))
        self.assertEqual(Specimen.objects.count(), 0)

    def test_seed_and_clear_reject_get(self):
        self.assertEqual(self.client.get(reverse('lab:performance:volume_seed')).status_code, 405)
        self.assertEqual(self.client.get(reverse('lab:performance:volume_clear')).status_code, 405)

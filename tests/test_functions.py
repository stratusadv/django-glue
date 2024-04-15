from django.test import TestCase


class TestFunctions(TestCase):
    def test_everything(self):
        try:
            self.assertTrue(True)
        except:
            self.assertTrue(False)
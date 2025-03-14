from unittest import TestCase

class TestDjangoGlue(TestCase):
    def test_import(self):
        try:
            import django_glue as dp

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)


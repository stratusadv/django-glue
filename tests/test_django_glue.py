from tests.test_base import BaseTestCase


class TestDjangoGlue(BaseTestCase):
    def test_import(self):
        try:
            import django_glue as dp

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)


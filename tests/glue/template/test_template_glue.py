from tests.test_base import BaseTestCase

import django_glue as dg


class TestTemplateGlue(BaseTestCase):
    def test_glue(self):
        try:
            dg.glue_template(
                self.request,
                'person_template',
                target='person_template.html'
            )

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)


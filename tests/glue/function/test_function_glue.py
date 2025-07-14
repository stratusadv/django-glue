from test_project.app.people.utils import check_name_is_valid
from tests.test_base import BaseTestCase

import django_glue as dg


class TestFunctionGlue(BaseTestCase):
    def test_glue(self):
        try:
            dg.glue_function(
                self.request,
                'person_function',
                'test_project.app.people.utils.check_name_is_valid'
            )

            self.assertTrue(True)
        except ImportError:
            self.assertTrue(False)


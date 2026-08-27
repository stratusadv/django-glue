import re

from django.template import RequestContext, Template
from django.test import RequestFactory, TestCase

from django_glue import constants
from django_glue.assets import asset_version


class AssetVersionTestCase(TestCase):
    def test_asset_version_is_package_version_plus_bundle_hash(self):
        version = asset_version()

        self.assertRegex(version, rf'^{re.escape(constants.__VERSION__)}\.[0-9a-f]{{8}}$')
        self.assertEqual(asset_version(), version)

    def test_init_tag_versions_the_bundle_url_by_content(self):
        request = RequestFactory().get('/')
        request.session = self.client.session
        template = Template('{% load django_glue %}{% django_glue_init %}')

        html = template.render(RequestContext(request, {}))

        self.assertIn(f'django_glue.js?v={asset_version()}"', html)

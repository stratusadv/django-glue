import re
from pathlib import Path

from django.test import TestCase

from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE


class GlueMapsSyncTestCase(TestCase):
    """Ensure Python and JavaScript SUBJECT_TYPE_TO_PROXY_* maps have identical keys."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Resolve path to the JS index file relative to the project root
        project_root = Path(__file__).resolve().parents[2]
        js_path = project_root / "client_js" / "src" / "proxies" / "index.js"
        cls.js_content = js_path.read_text(encoding="utf-8")

    def test_python_and_js_subject_type_keys_match(self):
        """The keys in maps.py and index.js must be identical."""
        # Extract keys from JS: look for string literals as keys in SUBJECT_TYPE_TO_PROXY_CLASS
        js_keys = set(re.findall(r"'(\w+)':\s*\w+", self.js_content))

        py_keys = set(SUBJECT_TYPE_TO_PROXY_TYPE.keys())

        missing_in_js = py_keys - js_keys
        missing_in_py = js_keys - py_keys

        if missing_in_js or missing_in_py:
            parts = []
            if missing_in_js:
                parts.append(f"Keys in Python but not JS: {missing_in_js}")
            if missing_in_py:
                parts.append(f"Keys in JS but not Python: {missing_in_py}")
            self.fail("\n  ".join(parts))

    def test_python_subject_type_keys_expected(self):
        """Verify the expected set of keys is present."""
        expected = {"Model", "QuerySet", "BaseForm", "Template"}
        self.assertEqual(set(SUBJECT_TYPE_TO_PROXY_TYPE.keys()), expected)

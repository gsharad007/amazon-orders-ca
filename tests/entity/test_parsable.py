__copyright__ = "Copyright (c) 2024-2025 Alex Laird"
__license__ = "MIT"

from bs4 import BeautifulSoup

from amazonorders.entity.parsable import Parsable
from tests.unittestcase import UnitTestCase


class TestItem(UnitTestCase):
    def test_to_currency(self):
        # GIVEN
        html = "<html />"
        parsed = BeautifulSoup(html, self.test_config.bs4_parser)

        # WHEN
        parsable = Parsable(parsed, self.test_config)

        # THEN
        self.assertIsNone(parsable.to_currency(None))
        self.assertIsNone(parsable.to_currency(""))
        self.assertEqual(parsable.to_currency(1234.99), 1234.99)
        self.assertEqual(parsable.to_currency(1234), 1234)
        self.assertEqual(parsable.to_currency("1,234.99"), 1234.99)
        self.assertEqual(parsable.to_currency("$1,234.99"), 1234.99)
        self.assertIsNone(parsable.to_currency("not currency"))

    def test_with_base_url_inferred_from_script(self):
        # GIVEN
        html = (
            "<html><head><script>ue_sn = 'www.amazon.com',</script></head>"
            "<body><a href='/gp/test'>Test</a></body></html>"
        )
        parsed = BeautifulSoup(html, self.test_config.bs4_parser)

        # WHEN
        parsable = Parsable(parsed, self.test_config)
        link = parsable.simple_parse("a", attr_name="href")

        # THEN
        self.assertEqual(link, "https://www.amazon.com/gp/test")

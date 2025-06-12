__copyright__ = "Copyright (c) 2024-2025 Alex Laird"
__license__ = "MIT"

import os

from bs4 import BeautifulSoup

from amazonorders.entity.order import Order
from amazonorders import util
from tests.unittestcase import UnitTestCase


class TestOrder(UnitTestCase):
    def test_order_currency_stripped(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-currency-stripped-snippet.html"),
                  "r",
                  encoding="utf-8") as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertEqual(order.item_subtotal, 1111.99)
        self.assertEqual(order.item_shipping_and_handling, 2222.99)
        self.assertEqual(order.total_before_tax, 3333.99)
        self.assertEqual(order.estimated_tax, 4444.99)
        self.assertIsNone(order.refund_total)
        self.assertIsNone(order.subscription_discount)
        self.assertEqual(order.grand_total, 7777.99)

    def test_order_invoice_link(self):
        # GIVEN
        with open(
            os.path.join(self.RESOURCES_DIR, "orders", "order-currency-stripped-snippet.html"),
            "r",
            encoding="utf-8",
        ) as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertIn("/gp/css/summary/print.html", order.invoice_link)

    def test_order_promotion_applied(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-promotion-applied-snippet.html"),
                  "r",
                  encoding="utf-8") as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertEqual(order.item_promotion, -0.05)

    def test_order_coupon_savings(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-details-coupon-savings.html"),
                  "r",
                  encoding="utf-8") as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertEqual(order.coupon_savings, -3.89)

    def test_order_free_shipping(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-details-111-6778632-7354601.html"),
                  "r",
                  encoding="utf-8") as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertEqual(order.free_shipping, -2.99)

    def test_order_coupon_savings_multiple(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-details-coupon-savings-multiple.html"),
                  "r",
                  encoding="utf-8") as f:
            parsed = BeautifulSoup(f.read(), self.test_config.bs4_parser)

        # WHEN
        order = Order(parsed, self.test_config, full_details=True)

        # THEN
        self.assertEqual(order.coupon_savings, -1.29)

    def test_recipient_prefers_details(self):
        """Recipient parsed from order details should override clone data."""
        # GIVEN clone order from history
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-2024-0.html"),
                  "r", encoding="utf-8") as f:
            history_soup = BeautifulSoup(f.read(), self.test_config.bs4_parser)
        order_tag = util.select(history_soup, self.test_config.selectors.ORDER_HISTORY_ENTITY_SELECTOR)[0]
        clone_order = Order(order_tag, self.test_config)

        # Sanity check clone recipient
        self.assertEqual("Alex Laird", clone_order.recipient.name)

        # GIVEN order details with different recipient name
        with open(
            os.path.join(self.RESOURCES_DIR, "orders", "order-details-112-5939971-8962610-mod.html"),
            "r", encoding="utf-8"
        ) as f:
            details_soup = BeautifulSoup(f.read(), self.test_config.bs4_parser)
        details_tag = util.select_one(details_soup, self.test_config.selectors.ORDER_DETAILS_ENTITY_SELECTOR)

        # WHEN
        order = Order(details_tag, self.test_config, full_details=True, clone=clone_order)

        # THEN details recipient should override
        self.assertEqual("John Doe", order.recipient.name)

__copyright__ = "Copyright (c) 2024-2025 Alex Laird"
__license__ = "MIT"

import os
import unittest
from datetime import date

import responses

from amazonorders.exception import AmazonOrdersError
from amazonorders.orders import AmazonOrders
from amazonorders.session import AmazonSession
from tests.unittestcase import UnitTestCase


class TestOrders(UnitTestCase):
    temp_order_history_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "output",
                                                "temp-order-history.html")
    temp_order_details_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "output",
                                                "temp-order-details.html")

    def setUp(self):
        super().setUp()

        self.amazon_session = AmazonSession("some-username",
                                            "some-password",
                                            config=self.test_config)

        self.amazon_orders = AmazonOrders(self.amazon_session)

    def test_get_orders_unauthenticated(self):
        # WHEN
        with self.assertRaises(AmazonOrdersError):
            self.amazon_orders.get_order_history()

    @responses.activate
    def test_get_order_history(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2018
        resp = self.given_order_history_exists(year)

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_112_0399923_3070642(orders[3], False)
        self.assertEqual(3, orders[3].index)
        self.assert_orders_list_index(orders)
        self.assertEqual(1, resp.call_count)

    @responses.activate
    def test_get_order_history_2024_data_component(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        resp = self.given_order_history_exists(year)

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        # Regular order with new `data-component` fields
        self.assert_order_112_5939971_8962610_data_component(orders[0], False)
        # Gift card order
        self.assert_order_112_4482432_2955442_gift_card(orders[2], False)
        # Digital order (legacy)
        self.assert_order_112_9087159_1657009_digital_order_legacy(orders[3], False)
        # Subscription order
        self.assert_order_114_8722141_6545058_data_component_subscription(orders[6], False)
        self.assertEqual(1, resp.call_count)

    @responses.activate
    def test_get_order_history_2025_gift_card(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-egift.html"), "r",
                  encoding="utf-8") as f:
            resp = responses.add(
                responses.GET,
                self.test_config.constants.ORDER_HISTORY_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assertEqual(1, resp.call_count)
        order = orders[5]
        self.assertEqual("112-8022032-9113020", order.order_id)
        self.assertEqual(150.00, order.grand_total)
        self.assertIsNotNone(order.order_details_link)
        self.assertEqual(date(2024, 10, 28), order.order_date)
        self.assertEqual(1, len(order.items))
        self.assertEqual("Amazon eGift Card - Birthday Candles (Animated)",
                         order.items[0].title)
        self.assertIsNotNone(order.items[0].link)
        self.assertIsNotNone(order.items[0].image_link)

    @responses.activate
    def test_get_order_history_2025_amazon_store(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-amazon-store.html"), "r",
                  encoding="utf-8") as f:
            resp = responses.add(
                responses.GET,
                self.test_config.constants.ORDER_HISTORY_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assertEqual(1, resp.call_count)
        order = orders[9]
        self.assertEqual("113-9085096-9353021", order.order_id)
        self.assertEqual(15.78, order.grand_total)
        self.assertIsNotNone(order.order_details_link)
        self.assertEqual(date(2025, 2, 28), order.order_date)
        self.assertEqual(0, len(order.items))

    @responses.activate
    def test_get_order_history_paginated(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2010
        resp1 = self.given_order_history_exists(year, start_index=0)
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-history-{year}-10.html"), "r",
                  encoding="utf-8") as f:
            resp2 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_HISTORY_URL}?timeFilter=year-{year}"
                "&startIndex=10&ref_=ppx_yo2ov_dt_b_pagination_1_2",
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year)

        # THEN
        self.assertEqual(12, len(orders))
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)

    @responses.activate
    def test_get_order_history_fresh(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-fresh.html"), "r",
                  encoding="utf-8") as f:
            resp = responses.add(
                responses.GET,
                self.test_config.constants.ORDER_HISTORY_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assertEqual(1, resp.call_count)
        order = orders[4]
        self.assertEqual("111-2072777-8279433", order.order_id)
        self.assertEqual(4, order.index)
        self.assertEqual(80.27, order.grand_total)
        self.assertIsNotNone(order.order_details_link)
        self.assertEqual(date(2025, 1, 3), order.order_date)
        self.assertEqual(0, len(order.items))

    @responses.activate
    def test_get_order_history_wholefoods(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-wholefoods.html"), "r",
                  encoding="utf-8") as f:
            resp = responses.add(
                responses.GET,
                self.test_config.constants.ORDER_HISTORY_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assertEqual(1, resp.call_count)
        order = orders[7]
        self.assertEqual("113-6307059-7336242", order.order_id)
        self.assertEqual(62.92, order.grand_total)
        self.assertIsNotNone(order.order_details_link)
        self.assertEqual(date(2024, 12, 12), order.order_date)
        self.assertEqual(0, len(order.items))

    @responses.activate
    def test_get_order_history_full_details_wholefood_skip(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(os.path.join(self.RESOURCES_DIR, "orders", "order-history-wholefoods-catering.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                self.test_config.constants.ORDER_HISTORY_URL,
                body=f.read(),
                status=200,
            )
        resp2 = self.given_any_order_details_exists("order-details-114-9460922-7737063.html")

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year, keep_paging=False, full_details=True)

        # THEN
        self.assertEqual(10, len(orders))
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(6, resp2.call_count)

    @responses.activate
    def test_get_order_history_full_details(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2020
        start_index = 40
        resp1 = self.given_order_history_exists(year, start_index)
        resp2 = self.given_any_order_details_exists("order-details-114-9460922-7737063.html")

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      start_index=start_index,
                                                      keep_paging=False,
                                                      full_details=True)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_114_9460922_7737063(orders[3], True)
        self.assertEqual(43, orders[3].index)
        self.assert_orders_list_index(orders)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(10, resp2.call_count)

    @responses.activate
    def test_get_order_history_multiple_items(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2020
        start_index = 40
        resp1 = self.given_order_history_exists(year, start_index)
        resp2 = self.given_any_order_details_exists("order-details-113-1625648-3437067.html")

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      start_index=start_index,
                                                      keep_paging=False,
                                                      full_details=True)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_113_1625648_3437067_multiple_items(orders[6], True)
        self.assertEqual(43, orders[3].index)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(10, resp2.call_count)

    @responses.activate
    def test_get_order_history_return(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2020
        start_index = 50
        resp1 = self.given_order_history_exists(year, start_index)
        resp2 = self.given_any_order_details_exists("order-details-112-2961628-4757846.html")

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      start_index=start_index,
                                                      keep_paging=False,
                                                      full_details=True)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_112_2961628_4757846_return(orders[1], True)
        self.assertEqual(53, orders[3].index)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(10, resp2.call_count)

    @responses.activate
    def test_get_order_history_quantity(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2020
        start_index = 50
        resp = self.given_order_history_exists(year, start_index)

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      start_index=start_index,
                                                      keep_paging=False)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_112_8888666_5244209_quantity(orders[7])
        self.assertEqual(53, orders[3].index)
        self.assertEqual(1, resp.call_count)

    @responses.activate
    def test_get_order_history_multiple_items_shipments_sellers(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2023
        start_index = 10
        resp1 = self.given_order_history_exists(year, start_index)
        resp2 = self.given_any_order_details_exists("order-details-112-9685975-5907428.html")

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      start_index=start_index,
                                                      keep_paging=False,
                                                      full_details=True)

        # THEN
        self.assertEqual(10, len(orders))
        self.assert_order_112_9685975_5907428_multiple_items_shipments_sellers(orders[3], True)
        self.assertEqual(13, orders[3].index)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(10, resp2.call_count)

    @responses.activate
    def test_get_order(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "112-9685975-5907428"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_112_9685975_5907428_multiple_items_shipments_sellers(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_data_component(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "112-5939971-8962610"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_112_5939971_8962610_data_component(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_gift_card(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "112-4482432-2955442"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_112_4482432_2955442_gift_card(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_digital_order_legacy(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "112-9087159-1657009"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_112_9087159_1657009_digital_order_legacy(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_digital_order_rd(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "D01-9262519-8073835"
        with open(
            os.path.join(
                self.RESOURCES_DIR, "orders", f"order-summary-{order_id}.html"
            ),
            "r",
            encoding="utf-8",
        ) as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_D01_9262519_8073835_digital_order_rd(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_data_component_subscription(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "114-8722141-6545058"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_114_8722141_6545058_data_component_subscription(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_2024_data_component_multiple_shipments(self):
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "111-6778632-7354601"
        with open(os.path.join(self.RESOURCES_DIR, "orders", f"order-details-{order_id}.html"), "r",
                  encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN
        self.assert_order_111_6778632_7354601_data_component_subscription(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_701_2278739_3285841(self):
        self.amazon_session.is_authenticated = True
        order_id = "701-2278739-3285841"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_701_2278739_3285841(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_701_3612180_7995405(self):
        self.amazon_session.is_authenticated = True
        order_id = "701-3612180-7995405"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_701_3612180_7995405(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_701_6757693_8305065(self):
        self.amazon_session.is_authenticated = True
        order_id = "701-6757693-8305065"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_701_6757693_8305065(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_701_2605741_0401037(self):
        self.amazon_session.is_authenticated = True
        order_id = "701-2605741-0401037"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_701_2605741_0401037(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_702_6894076_1433805(self):
        self.amazon_session.is_authenticated = True
        order_id = "702-6894076-1433805"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_702_6894076_1433805(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_D01_9338000_4893015(self):
        self.amazon_session.is_authenticated = True
        order_id = "D01-9338000-4893015"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-summary-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_D01_9338000_4893015_digital_order(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_701_3815833_5602607(self):
        self.amazon_session.is_authenticated = True
        order_id = "701-3815833-5602607"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_701_3815833_5602607(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_702_9503699_0712205(self):
        self.amazon_session.is_authenticated = True
        order_id = "702-9503699-0712205"
        with open(os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_702_9503699_0712205(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_702_7200239_3881040(self):
        self.amazon_session.is_authenticated = True
        order_id = "702-7200239-3881040"
        with open(
            os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"),
            "r",
            encoding="utf-8",
        ) as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_702_7200239_3881040(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_702_7633140_4494667(self):
        self.amazon_session.is_authenticated = True
        order_id = "702-7633140-4494667"
        with open(
            os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"),
            "r",
            encoding="utf-8",
        ) as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_702_7633140_4494667(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)

    @responses.activate
    def test_get_order_702_8836580_6196229(self):
        self.amazon_session.is_authenticated = True
        order_id = "702-8836580-6196229"
        with open(
            os.path.join(self.RESOURCES_DIR, "orders", "2024", f"order-details-{order_id}.html"),
            "r",
            encoding="utf-8",
        ) as f:
            resp1 = responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )
        order = self.amazon_orders.get_order(order_id)
        self.assert_order_702_8836580_6196229(order, True)
        self.assertIsNone(order.index)
        self.assertEqual(1, resp1.call_count)
    @unittest.skipIf(not os.path.exists(temp_order_history_file_path),
                     reason="Skipped, to debug an order history page, "
                            "place it at tests/output/temp-order-history.html")
    @responses.activate
    def test_temp_order_history_file(self):
        """
        This test can be used to drop in an order history page at tests/output/temp-order-history.html to easily
        run a test against it for debugging purposes.
        """
        # GIVEN
        self.amazon_session.is_authenticated = True
        year = 2024
        with open(self.temp_order_history_file_path, "r", encoding="utf-8") as f:
            responses.add(
                responses.GET,
                "{url}?timeFilter=year-{year}".format(url=self.test_config.constants.ORDER_HISTORY_URL,
                                                      year=year),
                body=f.read(),
                status=200,
            )

        # WHEN
        orders = self.amazon_orders.get_order_history(year=year,
                                                      keep_paging=False)

        # THEN, assert the primary fields are populated without regression
        for order in orders:
            self.assert_populated_generic(order, full_details=False)
            self.assertIsNotNone(order.index)

    @unittest.skipIf(not os.path.exists(temp_order_details_file_path),
                     reason="Skipped, to debug an order details page, "
                            "place it at tests/output/temp-order-details.html")
    @responses.activate
    def test_temp_order_details_file(self):
        """
        This test can be used to drop in an order details page at tests/output/temp-order-details.html to easily
        run a test against it for debugging purposes.
        """
        # GIVEN
        self.amazon_session.is_authenticated = True
        order_id = "temp-1234"
        with open(self.temp_order_details_file_path, "r", encoding="utf-8") as f:
            responses.add(
                responses.GET,
                f"{self.test_config.constants.ORDER_DETAILS_URL}?orderID={order_id}",
                body=f.read(),
                status=200,
            )

        # WHEN
        order = self.amazon_orders.get_order(order_id)

        # THEN, assert the primary fields are populated without regression
        self.assert_populated_generic(order, full_details=False)
        self.assertIsNone(order.index)

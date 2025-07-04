__copyright__ = "Copyright (c) 2024-2025 Alex Laird"
__license__ = "MIT"

import json
import html
import logging
from datetime import date, timedelta
from typing import Any, List, Optional, TypeVar, Union

from bs4 import BeautifulSoup, Tag

from amazonorders import util
from amazonorders.conf import AmazonOrdersConfig
from amazonorders.entity.item import Item
from amazonorders.entity.parsable import Parsable
from amazonorders.entity.recipient import Recipient
from amazonorders.entity.shipment import Shipment
from amazonorders.exception import AmazonOrdersError, AmazonOrdersEntityError
from dateutil import parser
import re

logger = logging.getLogger(__name__)

OrderEntity = TypeVar("OrderEntity", bound="Order")


class Order(Parsable):
    """
    An Amazon Order. If desired fields are populated as ``None``, ensure ``full_details`` is ``True`` when
    retrieving the Order (for instance, with :func:`~amazonorders.orders.AmazonOrders.get_order_history`), since
    by default it is ``False`` (it will slow down querying).
    """

    def __init__(self,
                 parsed: Tag,
                 config: AmazonOrdersConfig,
                 full_details: bool = False,
                 clone: Optional[OrderEntity] = None,
                 index: Optional[int] = None) -> None:
        super().__init__(parsed, config)

        #: If the Orders full details were populated from its details page.
        self.full_details: bool = full_details

        #: Where the Order appeared in the history when it was queried. This will inevitably change (ex. when a new
        #: order is placed, all indexes will then be off by one), but is still captured as it may be applicable in
        #: various use-cases. Only set when the Order is populated through
        #: :func:`~amazonorders.orders.AmazonOrders.get_order_history` (use ``start_index`` to correlate).
        self.index: Optional[int] = index

        #: The Order Shipments. Prefer Order Details info when available.
        if full_details or not clone:
            self.shipments: List[Shipment] = self._parse_shipments()
        else:
            self.shipments: List[Shipment] = clone.shipments
        #: The Order Items.
        self.items: List[Item] = clone.items if clone and not full_details else self._parse_items()
        self.title: str = " + ".join(str(item) for item in self.items) if self.items else ""
        self.item_quantity: int = max(len(self.items), 1)
        #: The Order number. Prefer Order Details info when available.
        parsed_order_id = self.safe_parse(self._parse_order_id)
        if parsed_order_id is None and clone is None:
            parsed_order_id = self.safe_parse(self._parse_order_id, required=True)
        self.order_id: str = parsed_order_id if parsed_order_id else (clone.order_id if clone else None)
        self.payment_reference_id: str = self.order_id + (
            f"-{self.index}" if self.index is not None else ""
        )
        #: The Order details link.
        parsed_details_link = self.safe_parse(self._parse_order_details_link)
        self.order_details_link: Optional[str] = parsed_details_link if parsed_details_link else (
            clone.order_details_link if clone else None)
        #: The Order invoice link.
        parsed_invoice_link = self.safe_parse(self._parse_invoice_link)
        if parsed_invoice_link:
            self.invoice_link: Optional[str] = parsed_invoice_link
        elif clone and clone.invoice_link:
            self.invoice_link = clone.invoice_link
        else:
            self.invoice_link = None
        #: The Order grand total.
        parsed_grand_total = self.safe_parse(self._parse_grand_total)
        self.grand_total: float = parsed_grand_total if parsed_grand_total is not None else (
            clone.grand_total if clone else 0.0)
        self.item_net_total: float = self.grand_total
        self.payment_amount: float = self.grand_total
        #: The Order placed date.
        parsed_order_date = self.safe_parse(self._parse_order_date)
        if parsed_order_date is None and clone is None:
            parsed_order_date = self.safe_parse(self._parse_order_date, required=True)
        self.order_date: date = parsed_order_date if parsed_order_date else (
            clone.order_date if clone else None)
        self.payment_date: date = self.order_date + timedelta(days=1)
        #: The Order Recipients.
        parsed_recipient = self.safe_parse(self._parse_recipient)
        self.recipient: Optional[Recipient] = parsed_recipient if parsed_recipient else (
            clone.recipient if clone else None)

        # Fields below this point are only populated if `full_details` is True

        #: The Order payment method. Only populated when ``full_details`` is ``True``.
        self.payment_method: Optional[str] = self._if_full_details(
            self.safe_simple_parse(selector=self.config.selectors.FIELD_ORDER_PAYMENT_METHOD_SELECTOR,
                                   attr_name="alt"))
        #: The Order payment method's last 4 digits. Only populated when ``full_details`` is ``True``.
        self.payment_method_last_4: Optional[str] = self._if_full_details(
            self.safe_simple_parse(selector=self.config.selectors.FIELD_ORDER_PAYMENT_METHOD_LAST_4_SELECTOR,
                                   prefix_split="ending in"))
        #: The Order item_subtotal. Only populated when ``full_details`` is ``True``.
        self.item_subtotal: Optional[float] = self._if_full_details(self._parse_currency("subtotal")) or 0.0
        #: The Order shipping total. Only populated when ``full_details`` is ``True``.
        self.shipping_total: Optional[float] = self._if_full_details(self._parse_currency("shipping")) or 0.0
        #: The Order free shipping. Only populated when ``full_details`` is ``True``.
        self.free_shipping: Optional[float] = self._if_full_details(self._parse_currency("free shipping")) or 0.0
        self.item_shipping_and_handling: Optional[float] = (
            (self.shipping_total or 0.0) + (self.free_shipping or 0.0)
        )
        #: The Order promotion applied. Only populated when ``full_details`` is ``True``.
        self.promotion: float = self._if_full_details(
            self._parse_currency("promotion", combine_multiple=True)) or 0.0
        #: The Order coupon savings. Only populated when ``full_details`` is ``True``.
        self.coupon_savings: float = self._if_full_details(
            self._parse_currency("coupon", combine_multiple=True)) or 0.0
        #: The Order Subscribe & Save discount. Only populated when ``full_details`` is ``True``.
        self.subscription_discount: float = self._if_full_details(self._parse_currency("subscribe")) or 0.0
        #: The Order paid by amazon applied. Only populated when ``full_details`` is ``True``.
        self.other_promotions: float = (
            self._if_full_details(
                self._parse_currency("amount paid by amazon", combine_multiple=True)
            )
            or 0.0
        )
        self.item_promotion: float = (
            (self.promotion or 0.0)
            + (self.coupon_savings or 0.0)
            + (self.subscription_discount or 0.0)
            + (self.other_promotions or 0.0)
        )
        #: The Order total before tax. Only populated when ``full_details`` is ``True``.
        self.total_before_tax: Optional[float] = self._if_full_details(self._parse_currency("total before tax"))
        #: The Order estimated tax. Only populated when ``full_details`` is ``True``.
        self.estimated_tax: Optional[float] = self._if_full_details(self._parse_currency("estimated tax"))
        #: The Order estimated tax. Only populated when ``full_details`` is ``True``.
        self.item_federal_tax: float = self._if_full_details(self._parse_currency("hst")) or 0.0
        #: The Order estimated tax. Only populated when ``full_details`` is ``True``.
        self.item_provincial_tax: float = self._if_full_details(self._parse_currency("pst")) or 0.0
        self.item_regulatory_fee: float = self._if_full_details(self._parse_currency("fee")) or 0.0
        #: The Order refund total. Only populated when ``full_details`` is ``True``.
        self.refund_total: Optional[float] = self._if_full_details(self._parse_currency("refund total"))

        self.amazon_internal_product_category: Optional[str] = ""
        self.amazon_class: Optional[str] = ""
        self.amazon_commodity: Optional[str] = ""

    def __repr__(self) -> str:
        return f"<Order #{self.order_id}: \"{self.items}\">"

    def __str__(self) -> str:  # pragma: no cover
        return f"Order #{self.order_id}: {self.items}"

    def _parse_shipments(self) -> List[Shipment]:
        if not self.parsed or len(util.select(self.parsed, self.config.selectors.ORDER_SKIP_ITEMS)) > 0:
            return []

        shipments: List[Shipment] = [self.config.shipment_cls(x, self.config)
                                     for x in util.select(self.parsed,
                                                          self.config.selectors.SHIPMENT_ENTITY_SELECTOR)]
        shipments.sort()
        return shipments

    def _parse_items(self) -> List[Item]:
        if not self.parsed or len(util.select(self.parsed, self.config.selectors.ORDER_SKIP_ITEMS)) > 0:
            return []

        items: List[Item] = [
            self.config.item_cls(x, self.config)
            for x in util.select(
                self.parsed, self.config.selectors.ITEM_ENTITY_SELECTOR
            )
        ]

        if not items:
            items = self._parse_digital_items()

        items.sort()
        return items

    def _parse_digital_items(self) -> List[Item]:
        items: List[Item] = []

        for header in self.parsed.find_all("b", string=re.compile("Items Ordered", re.I)):
            table = header.find_parent("table")
            if not table:
                continue
            header_row = header.find_parent("tr")
            rows = header_row.find_next_siblings("tr") if header_row else []
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue

                left, right = cols[0], cols[1]

                link_tag = left.find("a")
                if link_tag:
                    title = link_tag.get_text(strip=True)
                    link = link_tag.get("href", "#")
                else:
                    b_tag = left.find("b")
                    title = b_tag.get_text(strip=True) if b_tag else left.get_text(strip=True)
                    link = "#"

                qty_match = re.search(r"Qty:\s*(\d+)", left.get_text())
                qty = qty_match.group(1) if qty_match else "1"

                seller_match = re.search(r"Sold\s+By:\s*([^\n<]+)", left.get_text())
                seller = seller_match.group(1).strip() if seller_match else ""

                price_text = right.get_text(strip=True)

                html = (
                    f"<div class='yohtmlc-item'>"
                    f"<span data-component='itemTitle'><a href='{link}'>{title}</a></span>"
                    f"<span class='a-color-price'>{price_text}</span>"
                )
                if seller:
                    html += (
                        f"<div data-component='orderedMerchant'>Sold by: {seller}</div>"
                    )
                html += f"<span class='od-item-view-qty'>{qty}</span></div>"

                items.append(self.config.item_cls(BeautifulSoup(html, self.config.bs4_parser), self.config))
            break

        return items

    def _parse_order_id(self, required: bool = False) -> Optional[str]:
        value = self.simple_parse(
            self.config.selectors.FIELD_ORDER_NUMBER_SELECTOR,
            prefix_split="#",
            prefix_split_fuzzy=True,
        )

        if not value:
            tag = util.select_one(self.parsed, "#searchOrdersInput")
            if tag:
                value = tag.get("value")

        if not value:
            match = re.search(r"[A-Z0-9]{3}-\d{7}-\d{7}", self.parsed.text)
            if match:
                value = match.group(0)

        if not value and required:
            raise AmazonOrdersEntityError(
                "When building {name}, field for selector `{selector}` was None, but this is not allowed.".format(
                    name=self.__class__.__name__,
                    selector=self.config.selectors.FIELD_ORDER_NUMBER_SELECTOR,
                )
            )

        return value

    def _parse_order_date(self, required: bool = False) -> Optional[date]:
        value = self.simple_parse(
            self.config.selectors.FIELD_ORDER_PLACED_DATE_SELECTOR,
            suffix_split="Order #",
            suffix_split_fuzzy=True,
            parse_date=True,
        )

        if not value:
            tag = util.select_one(self.parsed, "td[bgcolor='#ddddcc'] > b")
            if tag:
                m = re.search(r"Digital Order:\s*(.*)", tag.get_text(strip=True))
                if m:
                    try:
                        value = parser.parse(m.group(1), fuzzy=True).date()
                    except Exception:
                        value = None

        if not value and required:
            raise AmazonOrdersEntityError(
                "When building {name}, field for selector `{selector}` was None, but this is not allowed.".format(
                    name=self.__class__.__name__,
                    selector=self.config.selectors.FIELD_ORDER_PLACED_DATE_SELECTOR,
                )
            )

        return value

    def _parse_order_details_link(self) -> Optional[str]:
        value = self.simple_parse(self.config.selectors.FIELD_ORDER_DETAILS_LINK_SELECTOR, attr_name="href")

        if not value and self.order_id:
            value = f"{self.config.constants.ORDER_DETAILS_URL}?orderID={self.order_id}"

        return value

    def _parse_invoice_link(self) -> Optional[str]:
        value = self.simple_parse(
            self.config.selectors.FIELD_ORDER_INVOICE_LINK_SELECTOR, attr_name="href"
        )

        if not value:
            popover = util.select_one(
                self.parsed, self.config.selectors.FIELD_ORDER_INVOICE_POPOVER_SELECTOR
            )
            if popover:
                data = popover.get("data-a-popover")
                if data:
                    try:
                        value = json.loads(html.unescape(data)).get("url")
                    except Exception:
                        value = None

        if not value and self.order_id:
            value = f"{self.config.constants.ORDER_INVOICE_MENU_URL}?orderId={self.order_id}"

        return value

    def _parse_grand_total(self) -> float:
        value = self.simple_parse(self.config.selectors.FIELD_ORDER_GRAND_TOTAL_SELECTOR)

        total_str = "total"

        if not value:
            for t in util.select(self.parsed, "td.a-text-right b"):
                if "Total for this Order" in t.text:
                    value = t.text.split(":")[-1]
                    break

        if not value:
            match = re.search(
                r"(Order Total|Total for this Order)[^$\d]*([$\d.,]+)",
                self.parsed.get_text(" ", strip=True),
            )
            if match:
                value = match.group(2)

        if not value:
            value = self._parse_currency("grand total")
        elif value.lower().startswith(total_str):
            value = value[len(total_str):].strip()

        value = self.to_currency(value)

        if value is None:
            raise AmazonOrdersError(
                "Order.grand_total did not populate, but it's required. "
                "Check if Amazon changed the HTML."
            )  # pragma: no cover

        return value

    def _parse_recipient(self) -> Optional[Recipient]:
        if util.select_one(
            self.parsed, self.config.selectors.FIELD_ORDER_GIFT_CARD_INSTANCE_SELECTOR
        ):
            return None

        value = util.select_one(self.parsed, self.config.selectors.FIELD_ORDER_ADDRESS_SELECTOR)

        if not value:
            value = util.select_one(self.parsed, self.config.selectors.FIELD_ORDER_ADDRESS_FALLBACK_1_SELECTOR)

            if value:
                data_popover = value.get("data-a-popover", {})  # type: ignore[arg-type, var-annotated]
                inline_content = data_popover.get("inlineContent")  # type: ignore[union-attr]
                if inline_content:
                    value = BeautifulSoup(json.loads(inline_content), self.config.bs4_parser)

        if not value:
            # TODO: there are multiple shipToData tags, we should double check we're picking the right one
            #  associated with the order; should also be able to eliminate the use of find_parent() here with
            #  a better CSS selector, we just need to make sure we have good test coverage around this path first
            parsed_parent = self.parsed.find_parent()

            if parsed_parent is None:
                raise AmazonOrdersError(
                    "Recipient parent not found, but it's required. "
                    "Check if Amazon changed the HTML."
                )  # pragma: no cover

            parent_tag = util.select_one(
                parsed_parent,
                self.config.selectors.FIELD_ORDER_ADDRESS_FALLBACK_2_SELECTOR
            )

            if parent_tag:
                value = BeautifulSoup(str(parent_tag.contents[0]).strip(), self.config.bs4_parser)

        if not value:
            m = re.search(
                r"Recipient:\s*([^\n]+)", self.parsed.get_text("\n", strip=True)
            )
            if m:
                value = BeautifulSoup(
                    f"<div><div>{m.group(1).strip()}</div></div>",
                    self.config.bs4_parser,
                )

        if not value:
            return None

        return Recipient(value, self.config)

    def _parse_currency(self, contains, combine_multiple=False) -> Optional[float]:
        value = None

        for tag in util.select(self.parsed, self.config.selectors.FIELD_ORDER_SUBTOTALS_TAG_ITERATOR_SELECTOR):
            if (contains in tag.text.lower() and
                    not util.select_one(tag,
                                        self.config.selectors.FIELD_ORDER_SUBTOTALS_TAG_POPOVER_PRELOAD_SELECTOR)):
                inner_tag = util.select_one(tag, self.config.selectors.FIELD_ORDER_SUBTOTALS_INNER_TAG_SELECTOR)
                if inner_tag:
                    currency = self.to_currency(inner_tag.text)
                    if currency is not None:
                        if value is None:
                            value = 0.0
                        value += currency

                    if not combine_multiple:
                        break
        if value is None:
            text = self.parsed.get_text(" ", strip=True)
            if contains == "estimated tax":
                matches = re.findall(
                    r"Tax \(.*?\):\s*([$\d.,]+)", text, flags=re.I
                )
            else:
                if contains in {"hst", "pst"}:
                    pattern = rf"Tax[^$\n]*\b{re.escape(contains)}\b[^$\d]*:\s*([$\d.,]+)"
                else:
                    pattern = rf"\b{re.escape(contains)}\b[^$\d]*:\s*([$\d.,]+)"
                matches = re.findall(pattern, text, flags=re.I)

            for m in matches:
                if "." not in m and "$" not in m and "," not in m:
                    continue
                currency = self.to_currency(m)
                if currency is not None:
                    if value is None:
                        value = 0.0
                    value += currency
                if not combine_multiple:
                    break

        return value

    def _if_full_details(self,
                         value: Any) -> Union[Any, None]:
        return value if self.full_details else None

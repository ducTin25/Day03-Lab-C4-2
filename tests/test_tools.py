"""Kiểm thử độc lập cho bộ tool đơn hàng và đổi/trả của Role 2."""

import json
import unittest

from src.tools import (
    AVAILABLE_TOOLS,
    MOCK_ORDERS,
    _reset_mock_state,
    check_return_eligibility,
    create_return_request,
    get_order_status,
    get_return_request_status,
)


def parse_result(result: str) -> dict:
    return json.loads(result)


class OrderToolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_mock_state()

    def test_registry_contains_four_tools(self) -> None:
        self.assertEqual(
            set(AVAILABLE_TOOLS),
            {
                "get_order_status",
                "check_return_eligibility",
                "create_return_request",
                "get_return_request_status",
            },
        )

    def test_demo_dataset_contains_exactly_fifty_orders(self) -> None:
        self.assertEqual(len(MOCK_ORDERS), 50)
        self.assertEqual(
            set(MOCK_ORDERS),
            {f"ORD-{number}" for number in range(1001, 1051)},
        )

    def test_get_order_status_success(self) -> None:
        result = parse_result(get_order_status("ORD-1001", "VC-01"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "ORDER_FOUND")
        self.assertEqual(result["data"]["status"], "delivered")

    def test_get_order_status_not_found(self) -> None:
        result = parse_result(get_order_status("ORD-9999", "VC-99"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "ORDER_NOT_FOUND")

    def test_get_order_status_verification_failed(self) -> None:
        result = parse_result(get_order_status("ORD-1001", "WRONG"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "VERIFICATION_FAILED")
        self.assertIsNone(result["data"])

    def test_get_order_status_invalid_input_does_not_crash(self) -> None:
        for invalid_value in (None, 123, ""):
            with self.subTest(invalid_value=invalid_value):
                result = parse_result(
                    get_order_status(invalid_value, "VC-01")
                )
                self.assertEqual(result["code"], "INVALID_INPUT")

    def test_eligibility_success(self) -> None:
        result = parse_result(
            check_return_eligibility(
                "ORD-1001", "ITEM-01", "damaged", "exchange"
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "RETURN_ELIGIBLE")

    def test_eligibility_order_not_delivered(self) -> None:
        result = parse_result(
            check_return_eligibility(
                "ORD-1002", "ITEM-03", "damaged", "exchange"
            )
        )
        self.assertEqual(result["code"], "ORDER_NOT_DELIVERED")

    def test_eligibility_window_expired(self) -> None:
        result = parse_result(
            check_return_eligibility(
                "ORD-1003", "ITEM-04", "defective", "refund"
            )
        )
        self.assertEqual(result["code"], "RETURN_WINDOW_EXPIRED")

    def test_eligibility_item_not_found(self) -> None:
        result = parse_result(
            check_return_eligibility(
                "ORD-1001", "ITEM-99", "damaged", "exchange"
            )
        )
        self.assertEqual(result["code"], "ITEM_NOT_FOUND")

    def test_eligibility_restricted_changed_mind(self) -> None:
        result = parse_result(
            check_return_eligibility(
                "ORD-1004", "ITEM-05", "changed_mind", "refund"
            )
        )
        self.assertEqual(result["code"], "ITEM_NOT_RETURNABLE")

    def test_eligibility_invalid_enums(self) -> None:
        invalid_reason = parse_result(
            check_return_eligibility(
                "ORD-1001", "ITEM-01", "unknown", "exchange"
            )
        )
        invalid_resolution = parse_result(
            check_return_eligibility(
                "ORD-1001", "ITEM-01", "damaged", "cash"
            )
        )
        self.assertEqual(invalid_reason["code"], "INVALID_REASON")
        self.assertEqual(
            invalid_resolution["code"], "INVALID_RESOLUTION"
        )

    def test_create_requires_confirmation(self) -> None:
        result = parse_result(
            create_return_request(
                "ORD-1001", "ITEM-01", "damaged", "exchange", False
            )
        )
        self.assertEqual(result["code"], "CONFIRMATION_REQUIRED")

    def test_create_success(self) -> None:
        result = parse_result(
            create_return_request(
                "ORD-1001", "ITEM-01", "damaged", "exchange", True
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "RETURN_REQUEST_CREATED")
        self.assertEqual(result["data"]["request_id"], "RET-0001")
        self.assertEqual(result["data"]["status"], "pending")

    def test_create_duplicate_request_is_blocked(self) -> None:
        create_return_request(
            "ORD-1001", "ITEM-01", "damaged", "exchange", True
        )
        duplicate = parse_result(
            create_return_request(
                "ORD-1001", "ITEM-01", "damaged", "exchange", True
            )
        )
        self.assertEqual(duplicate["code"], "DUPLICATE_REQUEST")

    def test_get_return_request_status_success(self) -> None:
        created = parse_result(
            create_return_request(
                "ORD-1001", "ITEM-01", "damaged", "exchange", True
            )
        )
        result = parse_result(
            get_return_request_status(
                created["data"]["request_id"], "VC-01"
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "RETURN_REQUEST_FOUND")

    def test_get_return_request_status_not_found(self) -> None:
        result = parse_result(
            get_return_request_status("RET-9999", "VC-01")
        )
        self.assertEqual(result["code"], "RETURN_REQUEST_NOT_FOUND")

    def test_status_verification_failed(self) -> None:
        create_return_request(
            "ORD-1001", "ITEM-01", "damaged", "exchange", True
        )
        result = parse_result(
            get_return_request_status("RET-0001", "WRONG")
        )
        self.assertEqual(result["code"], "VERIFICATION_FAILED")


if __name__ == "__main__":
    unittest.main()

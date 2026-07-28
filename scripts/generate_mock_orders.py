"""Sinh deterministic 50 đơn hàng giả lập cho demo.

Chạy từ thư mục gốc repo:
    python scripts/generate_mock_orders.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


REFERENCE_DATE = date(2026, 7, 28)
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "mock_orders.json"
)

PRODUCT_NAMES = [
    "Áo thun Basic",
    "Tai nghe Bluetooth",
    "Bàn phím cơ",
    "Chuột không dây",
    "Balo laptop",
    "Giày thể thao",
    "Bình nước cá nhân",
    "Sạc dự phòng",
    "Đèn bàn LED",
    "Cốc in tên theo yêu cầu",
]


def _item(
    item_id: str,
    name: str,
    quantity: int = 1,
    return_policy: str = "standard",
    return_window_days: int = 14,
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "name": name,
        "quantity": quantity,
        "return_policy": return_policy,
        "return_window_days": return_window_days,
    }


def _fixed_demo_orders() -> list[dict[str, Any]]:
    """Bốn đơn cố định tương thích với test case và tài liệu Role 1/2."""
    return [
        {
            "order_id": "ORD-1001",
            "verification_code": "VC-01",
            "status": "delivered",
            "ordered_at": "2026-07-22",
            "delivered_at": "2026-07-25",
            "payment_status": "paid",
            "items": [
                _item("ITEM-01", "Áo thun Basic"),
                _item(
                    "ITEM-02",
                    "Bình nước cá nhân",
                    return_policy="restricted",
                    return_window_days=7,
                ),
            ],
        },
        {
            "order_id": "ORD-1002",
            "verification_code": "VC-02",
            "status": "shipping",
            "ordered_at": "2026-07-27",
            "delivered_at": None,
            "payment_status": "paid",
            "items": [_item("ITEM-03", "Tai nghe Bluetooth")],
        },
        {
            "order_id": "ORD-1003",
            "verification_code": "VC-03",
            "status": "delivered",
            "ordered_at": "2026-06-20",
            "delivered_at": "2026-06-30",
            "payment_status": "paid",
            "items": [_item("ITEM-04", "Bàn phím cơ")],
        },
        {
            "order_id": "ORD-1004",
            "verification_code": "VC-04",
            "status": "delivered",
            "ordered_at": "2026-07-23",
            "delivered_at": "2026-07-26",
            "payment_status": "paid",
            "items": [
                _item(
                    "ITEM-05",
                    "Cốc in tên theo yêu cầu",
                    return_policy="restricted",
                    return_window_days=7,
                )
            ],
        },
    ]


def generate_orders() -> list[dict[str, Any]]:
    """Sinh đúng 50 đơn hàng, không dùng random để kết quả luôn ổn định."""
    orders = _fixed_demo_orders()
    status_cycle = [
        "delivered_recent",
        "shipping",
        "processing",
        "delivered_expired",
        "cancelled",
    ]

    for number in range(1005, 1051):
        sequence = number - 1000
        scenario = status_cycle[(sequence - 5) % len(status_cycle)]
        order_id = f"ORD-{number}"
        verification_code = f"VC-{sequence:02d}"
        ordered_at = REFERENCE_DATE - timedelta(days=sequence % 12 + 2)

        if scenario == "delivered_recent":
            status = "delivered"
            delivered_at = REFERENCE_DATE - timedelta(days=sequence % 6 + 1)
            payment_status = "paid"
        elif scenario == "delivered_expired":
            status = "delivered"
            delivered_at = REFERENCE_DATE - timedelta(days=20 + sequence % 15)
            payment_status = "paid"
        elif scenario == "shipping":
            status = "shipping"
            delivered_at = None
            payment_status = "paid"
        elif scenario == "processing":
            status = "processing"
            delivered_at = None
            payment_status = "pending"
        else:
            status = "cancelled"
            delivered_at = None
            payment_status = "refunded"

        product_index = sequence % len(PRODUCT_NAMES)
        second_product_index = (product_index + 3) % len(PRODUCT_NAMES)
        first_policy = "restricted" if sequence % 7 == 0 else "standard"
        second_policy = "restricted" if sequence % 4 == 0 else "standard"

        items = [
            _item(
                f"ITEM-{sequence:03d}-01",
                PRODUCT_NAMES[product_index],
                quantity=sequence % 2 + 1,
                return_policy=first_policy,
                return_window_days=7 if first_policy == "restricted" else 14,
            ),
            _item(
                f"ITEM-{sequence:03d}-02",
                PRODUCT_NAMES[second_product_index],
                return_policy=second_policy,
                return_window_days=7 if second_policy == "restricted" else 14,
            ),
        ]

        orders.append(
            {
                "order_id": order_id,
                "verification_code": verification_code,
                "status": status,
                "ordered_at": ordered_at.isoformat(),
                "delivered_at": (
                    delivered_at.isoformat() if delivered_at else None
                ),
                "payment_status": payment_status,
                "items": items,
            }
        )

    if len(orders) != 50:
        raise RuntimeError(f"Expected 50 orders, generated {len(orders)}")
    return orders


def main() -> None:
    orders = generate_orders()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(orders, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(orders)} orders at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

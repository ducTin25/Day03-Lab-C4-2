"""
Tool Registry dành cho đề tài:
Trợ lý Tra cứu Đơn hàng và Xử lý Đổi/Trả.

Các tool dùng dữ liệu giả lập deterministic, không gọi API bên ngoài và không
cần API key. Mọi kết quả được trả về dưới dạng JSON string để ReAct Agent có
thể dùng trực tiếp làm Observation.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


# Ngày tham chiếu cố định giúp kết quả kiểm thử không thay đổi theo ngày chạy.
REFERENCE_DATE = date(2026, 7, 28)

ALLOWED_REASONS = {
    "wrong_item",
    "damaged",
    "defective",
    "not_as_described",
    "changed_mind",
}
ALLOWED_RESOLUTIONS = {"exchange", "refund"}


# Dữ liệu dự phòng tối thiểu nếu file config/mock_orders.json chưa tồn tại.
# Không chứa tên, địa chỉ hay số điện thoại thật.
FALLBACK_MOCK_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-1001": {
        "verification_code": "VC-01",
        "status": "delivered",
        "ordered_at": "2026-07-22",
        "delivered_at": "2026-07-25",
        "payment_status": "paid",
        "items": [
            {
                "item_id": "ITEM-01",
                "name": "Áo thun Basic",
                "quantity": 1,
                "return_policy": "standard",
                "return_window_days": 14,
            },
            {
                "item_id": "ITEM-02",
                "name": "Bình nước cá nhân",
                "quantity": 1,
                "return_policy": "restricted",
                "return_window_days": 7,
            },
        ],
    },
    "ORD-1002": {
        "verification_code": "VC-02",
        "status": "shipping",
        "ordered_at": "2026-07-27",
        "delivered_at": None,
        "payment_status": "paid",
        "items": [
            {
                "item_id": "ITEM-03",
                "name": "Tai nghe Bluetooth",
                "quantity": 1,
                "return_policy": "standard",
                "return_window_days": 14,
            }
        ],
    },
    "ORD-1003": {
        "verification_code": "VC-03",
        "status": "delivered",
        "ordered_at": "2026-06-20",
        "delivered_at": "2026-06-30",
        "payment_status": "paid",
        "items": [
            {
                "item_id": "ITEM-04",
                "name": "Bàn phím cơ",
                "quantity": 1,
                "return_policy": "standard",
                "return_window_days": 14,
            }
        ],
    },
    "ORD-1004": {
        "verification_code": "VC-04",
        "status": "delivered",
        "ordered_at": "2026-07-23",
        "delivered_at": "2026-07-26",
        "payment_status": "paid",
        "items": [
            {
                "item_id": "ITEM-05",
                "name": "Cốc in tên theo yêu cầu",
                "quantity": 1,
                "return_policy": "restricted",
                "return_window_days": 7,
            }
        ],
    },
}


def _load_mock_orders() -> dict[str, dict[str, Any]]:
    """Đọc bộ dữ liệu demo từ config, fallback an toàn nếu file bị thiếu/lỗi."""
    data_path = (
        Path(__file__).resolve().parents[1] / "config" / "mock_orders.json"
    )
    try:
        records = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError("mock_orders.json phải là một list không rỗng.")

        orders: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Mỗi đơn hàng phải là một object.")
            order_id = record.get("order_id")
            if not _is_non_empty_string(order_id):
                raise ValueError("Mỗi đơn hàng phải có order_id hợp lệ.")
            normalized_order_id = order_id.strip().upper()
            if normalized_order_id in orders:
                raise ValueError(f"Trùng order_id: {normalized_order_id}")
            orders[normalized_order_id] = record
        return orders
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return deepcopy(FALLBACK_MOCK_ORDERS)


# Bộ dữ liệu thực tế được các tool sử dụng.
MOCK_ORDERS: dict[str, dict[str, Any]] = {}


# Kho yêu cầu đổi/trả giả lập có thay đổi trong thời gian chương trình chạy.
MOCK_RETURN_REQUESTS: dict[str, dict[str, Any]] = {}


def _response(
    ok: bool,
    code: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> str:
    """Tạo JSON string thống nhất cho mọi Observation của tool."""
    return json.dumps(
        {"ok": ok, "code": code, "message": message, "data": data},
        ensure_ascii=False,
        sort_keys=True,
    )


def _invalid_input(message: str) -> str:
    return _response(False, "INVALID_INPUT", message)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


# Chỉ tải dữ liệu sau khi helper validate đã được định nghĩa.
MOCK_ORDERS = _load_mock_orders()


def _find_item(order: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in order["items"] if item["item_id"] == item_id),
        None,
    )


def _find_open_request(order_id: str, item_id: str) -> dict[str, Any] | None:
    return next(
        (
            request
            for request in MOCK_RETURN_REQUESTS.values()
            if request["order_id"] == order_id
            and request["item_id"] == item_id
            and request["status"] in {"pending", "approved", "processing"}
        ),
        None,
    )


def get_order_status(
    order_id: str = "",
    verification_code: str = "",
) -> str:
    """
    Tra cứu trạng thái và thông tin tối thiểu của một đơn hàng.

    Purpose:
        Dùng khi người dùng muốn kiểm tra đơn hàng hoặc trước khi xử lý đổi/trả.
        Không dùng để thay đổi trạng thái đơn.
    Args:
        order_id: Mã đơn hàng, ví dụ ``ORD-1001``.
        verification_code: Mã xác minh giả lập, ví dụ ``VC-01``.
    Returns:
        JSON string theo schema ``ok/code/message/data``. Khi thành công, data
        chứa trạng thái, ngày giao, thanh toán và danh sách sản phẩm.
    Errors:
        ``INVALID_INPUT``, ``ORDER_NOT_FOUND``, ``VERIFICATION_FAILED`` hoặc
        ``INTERNAL_TOOL_ERROR``. Lỗi được trả về như dữ liệu, không raise.
    Side effects:
        Không có; đây là tool read-only.
    Example:
        ``get_order_status("ORD-1001", "VC-01")``.
    """
    try:
        if not _is_non_empty_string(order_id):
            return _invalid_input("order_id phải là chuỗi không rỗng.")
        if not _is_non_empty_string(verification_code):
            return _invalid_input("verification_code phải là chuỗi không rỗng.")

        normalized_order_id = order_id.strip().upper()
        order = MOCK_ORDERS.get(normalized_order_id)
        if order is None:
            return _response(
                False,
                "ORDER_NOT_FOUND",
                "Không tìm thấy đơn hàng.",
            )
        if verification_code.strip() != order["verification_code"]:
            return _response(
                False,
                "VERIFICATION_FAILED",
                "Mã xác minh không chính xác.",
            )

        public_items = [
            {
                "item_id": item["item_id"],
                "name": item["name"],
                "quantity": item["quantity"],
            }
            for item in order["items"]
        ]
        return _response(
            True,
            "ORDER_FOUND",
            "Đã tìm thấy đơn hàng.",
            {
                "order_id": normalized_order_id,
                "status": order["status"],
                "ordered_at": order["ordered_at"],
                "delivered_at": order["delivered_at"],
                "payment_status": order["payment_status"],
                "items": public_items,
            },
        )
    except Exception:
        return _response(
            False,
            "INTERNAL_TOOL_ERROR",
            "Không thể tra cứu đơn hàng do lỗi nội bộ.",
        )


def check_return_eligibility(
    order_id: str = "",
    item_id: str = "",
    reason: str = "",
    requested_resolution: str = "",
) -> str:
    """
    Kiểm tra một sản phẩm có đủ điều kiện đổi hoặc trả hàng hay không.

    Purpose:
        Dùng sau khi đã biết mã đơn và mã sản phẩm. Tool chỉ kiểm tra chính
        sách, không tạo yêu cầu và không thay đổi dữ liệu.
    Args:
        order_id: Mã đơn hàng.
        item_id: Mã sản phẩm thuộc đơn hàng.
        reason: Một trong ``wrong_item``, ``damaged``, ``defective``,
            ``not_as_described`` hoặc ``changed_mind``.
        requested_resolution: ``exchange`` hoặc ``refund``.
    Returns:
        JSON string. Khi đủ điều kiện, data chứa ``eligible=true``, hạn cuối,
        lý do và bước tiếp theo.
    Errors:
        ``INVALID_INPUT``, ``ORDER_NOT_FOUND``, ``ITEM_NOT_FOUND``,
        ``ORDER_NOT_DELIVERED``, ``RETURN_WINDOW_EXPIRED``,
        ``ITEM_NOT_RETURNABLE``, ``DUPLICATE_REQUEST`` hoặc lỗi nội bộ.
    Side effects:
        Không có; đây là tool read-only.
    Example:
        ``check_return_eligibility("ORD-1001", "ITEM-01", "damaged",
        "exchange")``.
    """
    try:
        values = {
            "order_id": order_id,
            "item_id": item_id,
            "reason": reason,
            "requested_resolution": requested_resolution,
        }
        for field_name, value in values.items():
            if not _is_non_empty_string(value):
                return _invalid_input(
                    f"{field_name} phải là chuỗi không rỗng."
                )

        normalized_order_id = order_id.strip().upper()
        normalized_item_id = item_id.strip().upper()
        normalized_reason = reason.strip().lower()
        normalized_resolution = requested_resolution.strip().lower()

        if normalized_reason not in ALLOWED_REASONS:
            return _response(
                False,
                "INVALID_REASON",
                "Lý do đổi/trả không hợp lệ.",
                {"allowed_reasons": sorted(ALLOWED_REASONS)},
            )
        if normalized_resolution not in ALLOWED_RESOLUTIONS:
            return _response(
                False,
                "INVALID_RESOLUTION",
                "Hình thức xử lý không hợp lệ.",
                {"allowed_resolutions": sorted(ALLOWED_RESOLUTIONS)},
            )

        order = MOCK_ORDERS.get(normalized_order_id)
        if order is None:
            return _response(
                False,
                "ORDER_NOT_FOUND",
                "Không tìm thấy đơn hàng.",
            )
        item = _find_item(order, normalized_item_id)
        if item is None:
            return _response(
                False,
                "ITEM_NOT_FOUND",
                "Không tìm thấy sản phẩm trong đơn hàng.",
            )
        if order["status"] != "delivered" or not order["delivered_at"]:
            return _response(
                False,
                "ORDER_NOT_DELIVERED",
                "Đơn hàng chưa được giao nên chưa thể yêu cầu đổi/trả.",
            )

        delivered_at = datetime.strptime(
            order["delivered_at"], "%Y-%m-%d"
        ).date()
        deadline = delivered_at + timedelta(
            days=item["return_window_days"]
        )
        if REFERENCE_DATE > deadline:
            return _response(
                False,
                "RETURN_WINDOW_EXPIRED",
                "Sản phẩm đã quá thời hạn đổi/trả.",
                {"deadline": deadline.isoformat()},
            )

        if (
            item["return_policy"] == "restricted"
            and normalized_reason == "changed_mind"
        ):
            return _response(
                False,
                "ITEM_NOT_RETURNABLE",
                "Sản phẩm hạn chế không được đổi/trả vì thay đổi ý định.",
            )

        existing_request = _find_open_request(
            normalized_order_id, normalized_item_id
        )
        if existing_request is not None:
            return _response(
                False,
                "DUPLICATE_REQUEST",
                "Sản phẩm đã có một yêu cầu đổi/trả đang xử lý.",
                {"request_id": existing_request["request_id"]},
            )

        return _response(
            True,
            "RETURN_ELIGIBLE",
            "Sản phẩm đủ điều kiện đổi/trả.",
            {
                "eligible": True,
                "order_id": normalized_order_id,
                "item_id": normalized_item_id,
                "reason": normalized_reason,
                "requested_resolution": normalized_resolution,
                "deadline": deadline.isoformat(),
                "next_action": "Yêu cầu người dùng xác nhận trước khi tạo yêu cầu.",
            },
        )
    except Exception:
        return _response(
            False,
            "INTERNAL_TOOL_ERROR",
            "Không thể kiểm tra điều kiện đổi/trả do lỗi nội bộ.",
        )


def create_return_request(
    order_id: str = "",
    item_id: str = "",
    reason: str = "",
    requested_resolution: str = "",
    confirmed: bool = False,
) -> str:
    """
    Tạo yêu cầu đổi hoặc trả hàng trong kho dữ liệu giả lập.

    Purpose:
        Chỉ dùng sau khi người dùng xác nhận rõ ràng và sản phẩm đủ điều kiện.
    Args:
        order_id: Mã đơn hàng.
        item_id: Mã sản phẩm.
        reason: Lý do đổi/trả hợp lệ.
        requested_resolution: ``exchange`` hoặc ``refund``.
        confirmed: Phải là boolean ``True`` từ xác nhận của người dùng.
    Returns:
        JSON string. Khi thành công, data chứa mã yêu cầu, trạng thái ban đầu,
        hình thức xử lý và bước tiếp theo.
    Errors:
        ``CONFIRMATION_REQUIRED`` nếu chưa xác nhận; các lỗi chính sách từ
        ``check_return_eligibility``; ``DUPLICATE_REQUEST`` hoặc lỗi nội bộ.
    Side effects:
        Có; thêm một bản ghi vào ``MOCK_RETURN_REQUESTS``. Tool chống tạo trùng.
    Safety:
        Chỉ thông báo đã tạo yêu cầu, không tuyên bố đã hoàn tiền hoặc đổi hàng.
    Example:
        ``create_return_request("ORD-1001", "ITEM-01", "damaged",
        "exchange", True)``.
    """
    try:
        if not isinstance(confirmed, bool):
            return _invalid_input("confirmed phải là giá trị boolean.")
        if not confirmed:
            return _response(
                False,
                "CONFIRMATION_REQUIRED",
                "Cần người dùng xác nhận trước khi tạo yêu cầu đổi/trả.",
            )

        eligibility_json = check_return_eligibility(
            order_id,
            item_id,
            reason,
            requested_resolution,
        )
        eligibility = json.loads(eligibility_json)
        if not eligibility["ok"]:
            return eligibility_json

        normalized_order_id = order_id.strip().upper()
        normalized_item_id = item_id.strip().upper()
        normalized_reason = reason.strip().lower()
        normalized_resolution = requested_resolution.strip().lower()
        request_id = f"RET-{len(MOCK_RETURN_REQUESTS) + 1:04d}"
        request = {
            "request_id": request_id,
            "order_id": normalized_order_id,
            "item_id": normalized_item_id,
            "reason": normalized_reason,
            "resolution": normalized_resolution,
            "status": "pending",
            "created_at": REFERENCE_DATE.isoformat(),
            "updated_at": REFERENCE_DATE.isoformat(),
            "next_action": "Chờ bộ phận chăm sóc khách hàng xét duyệt.",
        }
        MOCK_RETURN_REQUESTS[request_id] = request

        return _response(
            True,
            "RETURN_REQUEST_CREATED",
            "Đã tạo yêu cầu đổi/trả.",
            deepcopy(request),
        )
    except Exception:
        return _response(
            False,
            "INTERNAL_TOOL_ERROR",
            "Không thể tạo yêu cầu đổi/trả do lỗi nội bộ.",
        )


def get_return_request_status(
    request_id: str = "",
    verification_code: str = "",
) -> str:
    """
    Tra cứu trạng thái hiện tại của một yêu cầu đổi/trả.

    Purpose:
        Dùng khi người dùng đã có ``request_id`` và muốn xem tiến độ.
    Args:
        request_id: Mã yêu cầu, ví dụ ``RET-0001``.
        verification_code: Mã xác minh của đơn hàng liên quan.
    Returns:
        JSON string chứa trạng thái, thời gian cập nhật và bước tiếp theo.
    Errors:
        ``INVALID_INPUT``, ``RETURN_REQUEST_NOT_FOUND``,
        ``VERIFICATION_FAILED`` hoặc ``INTERNAL_TOOL_ERROR``.
    Side effects:
        Không có; đây là tool read-only.
    Example:
        ``get_return_request_status("RET-0001", "VC-01")``.
    """
    try:
        if not _is_non_empty_string(request_id):
            return _invalid_input("request_id phải là chuỗi không rỗng.")
        if not _is_non_empty_string(verification_code):
            return _invalid_input("verification_code phải là chuỗi không rỗng.")

        normalized_request_id = request_id.strip().upper()
        request = MOCK_RETURN_REQUESTS.get(normalized_request_id)
        if request is None:
            return _response(
                False,
                "RETURN_REQUEST_NOT_FOUND",
                "Không tìm thấy yêu cầu đổi/trả.",
            )

        order = MOCK_ORDERS[request["order_id"]]
        if verification_code.strip() != order["verification_code"]:
            return _response(
                False,
                "VERIFICATION_FAILED",
                "Mã xác minh không chính xác.",
            )

        public_request = {
            "request_id": request["request_id"],
            "order_id": request["order_id"],
            "item_id": request["item_id"],
            "resolution": request["resolution"],
            "status": request["status"],
            "created_at": request["created_at"],
            "updated_at": request["updated_at"],
            "next_action": request["next_action"],
        }
        return _response(
            True,
            "RETURN_REQUEST_FOUND",
            "Đã tìm thấy yêu cầu đổi/trả.",
            public_request,
        )
    except Exception:
        return _response(
            False,
            "INTERNAL_TOOL_ERROR",
            "Không thể tra cứu yêu cầu đổi/trả do lỗi nội bộ.",
        )


def _reset_mock_state() -> None:
    """Xóa yêu cầu phát sinh; chỉ dùng cho kiểm thử độc lập."""
    MOCK_RETURN_REQUESTS.clear()


# Danh sách tool được đăng ký để ReAct Agent sử dụng.
AVAILABLE_TOOLS = {
    "get_order_status": get_order_status,
    "check_return_eligibility": check_return_eligibility,
    "create_return_request": create_return_request,
    "get_return_request_status": get_return_request_status,
}

# Danh sách công cụ Role 2 - Tool Engineer

## Đề tài

**Trợ lý Tra cứu Đơn hàng và Xử lý Đổi/Trả**

Role 2 dự kiến xây dựng các công cụ sau trong file `src/tools.py`:

## 1. `get_order_status`

Tra cứu trạng thái và thông tin cơ bản của đơn hàng.

```python
get_order_status(order_id: str, verification_code: str) -> str
```

Chức năng chính:

- Kiểm tra mã đơn hàng.
- Xác minh người dùng bằng mã xác minh.
- Trả về trạng thái đơn hàng như đang xử lý, đang giao hoặc đã giao.
- Trả về danh sách sản phẩm cần thiết cho quy trình đổi/trả.

## 2. `check_return_eligibility`

Kiểm tra sản phẩm có đủ điều kiện đổi hoặc trả hàng không.

```python
check_return_eligibility(
    order_id: str,
    item_id: str,
    reason: str,
    requested_resolution: str
) -> str
```

Chức năng chính:

- Kiểm tra đơn hàng đã được giao chưa.
- Kiểm tra sản phẩm có thuộc đơn hàng không.
- Kiểm tra thời hạn đổi/trả.
- Kiểm tra lý do đổi/trả.
- Trả về kết quả đủ điều kiện hoặc lý do bị từ chối.

## 3. `create_return_request`

Tạo yêu cầu đổi hoặc trả hàng sau khi người dùng xác nhận.

```python
create_return_request(
    order_id: str,
    item_id: str,
    reason: str,
    requested_resolution: str,
    confirmed: bool
) -> str
```

Chức năng chính:

- Kiểm tra lại điều kiện đổi/trả.
- Yêu cầu người dùng xác nhận trước khi tạo yêu cầu.
- Tạo mã yêu cầu đổi/trả.
- Ngăn tạo nhiều yêu cầu trùng nhau cho cùng một sản phẩm.

## 4. `get_return_request_status`

Tra cứu trạng thái xử lý của yêu cầu đổi/trả.

```python
get_return_request_status(
    request_id: str,
    verification_code: str
) -> str
```

Chức năng chính:

- Kiểm tra mã yêu cầu đổi/trả.
- Xác minh người dùng.
- Trả về trạng thái hiện tại và bước xử lý tiếp theo.

## Đăng ký công cụ

Sau khi hoàn thành, các công cụ sẽ được đăng ký trong `AVAILABLE_TOOLS`:

```python
AVAILABLE_TOOLS = {
    "get_order_status": get_order_status,
    "check_return_eligibility": check_return_eligibility,
    "create_return_request": create_return_request,
    "get_return_request_status": get_return_request_status,
}
```

## Yêu cầu chung

- Mỗi công cụ có docstring mô tả rõ input, output và lỗi.
- Các công cụ trả về thông báo lỗi thay vì làm chương trình bị crash.
- Dữ liệu trả về có cấu trúc thống nhất để ReAct Agent dễ xử lý.
- Công cụ tạo yêu cầu đổi/trả phải có xác nhận của người dùng.
- Không để lộ thông tin cá nhân hoặc mã xác minh trong phản hồi.


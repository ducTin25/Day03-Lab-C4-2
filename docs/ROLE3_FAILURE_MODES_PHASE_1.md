# 🧠 Role 3 — Mốc 1: Failure Modes (Trợ Lý Tra Cứu Đơn Hàng & Xử Lý Đổi Trả)

> Phụ trách: Role 3 — Prompt Engineer
> Mục tiêu Mốc 1: Xác định các trường hợp tool có thể bị lỗi (Failure Modes), làm căn cứ viết `REACT_SYSTEM_PROMPT` và Guardrails ở Mốc 3 trong `src/prompts.py`.
> Căn cứ theo bộ tool & mã lỗi do Role 2 chốt trong `src/tools.py`: `get_order_status`, `check_return_eligibility`, `create_return_request`, `get_return_request_status`.

---

## 1. Failure Modes theo từng Tool

| Tool | Failure Mode | Mã lỗi (`code`) |
| :--- | :--- | :--- |
| `get_order_status` | Thiếu / sai kiểu `order_id`, `verification_code` | `INVALID_INPUT` |
| | Mã đơn không tồn tại | `ORDER_NOT_FOUND` |
| | Sai mã xác minh | `VERIFICATION_FAILED` |
| `check_return_eligibility` | Sản phẩm (`item_id`) không thuộc đơn | `ITEM_NOT_FOUND` |
| | Đơn chưa giao xong (trạng thái `shipping`) | `ORDER_NOT_DELIVERED` |
| | Quá hạn đổi/trả | `RETURN_WINDOW_EXPIRED` |
| | Sản phẩm thuộc nhóm không được đổi (hàng cá nhân hóa, vệ sinh cá nhân...) | `ITEM_NOT_RETURNABLE` |
| | `reason` không nằm trong enum (`wrong_item`, `damaged`, `defective`, `not_as_described`, `changed_mind`) | `INVALID_REASON` |
| | `requested_resolution` không hợp lệ (`exchange` / `refund`) | `INVALID_RESOLUTION` |
| `create_return_request` | Chưa có xác nhận rõ ràng (`confirmed != true`) | `CONFIRMATION_REQUIRED` |
| | Gọi tạo yêu cầu trùng cho cùng `order_id` + `item_id` đang mở | `DUPLICATE_REQUEST` |
| | Không đủ điều kiện đổi/trả (bỏ qua hoặc phớt lờ bước kiểm tra) | các mã của `check_return_eligibility` |
| `get_return_request_status` | Mã yêu cầu (`request_id`) không tồn tại | `RETURN_REQUEST_NOT_FOUND` |
| | Sai mã xác minh | `VERIFICATION_FAILED` |
| Mọi tool | Lỗi kỹ thuật không lường trước (exception nội bộ) | `INTERNAL_TOOL_ERROR` |

---

## 2. Failure Modes ở cấp Agent (ReAct Loop)

Đây là nhóm lỗi **tool không tự chặn được** — Role 3 phải "phanh" bằng System Prompt & Guardrails:

1. **Bịa Observation**: Agent tự sinh kết quả tool thay vì chờ dữ liệu thật trả về.
2. **Tạo yêu cầu khi chưa xác nhận**: Agent gọi `create_return_request` với `confirmed=true` dù người dùng chưa xác nhận rõ ràng.
3. **Bỏ qua bước kiểm tra điều kiện**: Agent gọi thẳng `create_return_request` mà chưa gọi `check_return_eligibility` trước.
4. **Lặp vô hạn**: Agent gặp lỗi (vd `ORDER_NOT_FOUND`) rồi gọi lại y hệt Action nhiều lần thay vì dừng/hỏi lại người dùng.
5. **Lộ dữ liệu nhạy cảm**: Agent đưa `verification_code` hoặc PII vào Final Answer / Observation hiển thị cho người dùng.
6. **Khẳng định sai kết quả**: Agent trả lời như đã hoàn tiền/đổi hàng xong, trong khi tool chỉ mới "tạo yêu cầu" ở trạng thái `pending`.
7. **Ngoài phạm vi / Prompt Injection**: Câu hỏi không liên quan đơn hàng/đổi trả, hoặc cố chèn lệnh yêu cầu đổi vai trò, bỏ qua luật của Agent.

---

## 3. Ánh xạ sang Guardrail (áp dụng ở Mốc 3 trong `src/prompts.py`)

| Failure Mode (Agent) | Guardrail tương ứng |
| :--- | :--- |
| Bịa Observation | Chỉ dùng dữ liệu thật do hệ thống trả về sau mỗi Action |
| Tạo yêu cầu khi chưa xác nhận | Bắt buộc hỏi xác nhận rõ ràng trước khi set `confirmed=true` |
| Bỏ qua bước kiểm tra điều kiện | Bắt buộc gọi `check_return_eligibility` trước `create_return_request` |
| Lặp vô hạn | Giới hạn `MAX_ITERATIONS`; không lặp lại Action giống hệt sau khi đã lỗi |
| Lộ dữ liệu nhạy cảm | Không đưa `verification_code`/PII vào Final Answer |
| Khẳng định sai kết quả | Chỉ thông báo đúng trạng thái tool trả về (vd `pending`), không suy diễn thêm |
| Ngoài phạm vi / Prompt Injection | Từ chối lịch sự, nhắc lại phạm vi hỗ trợ (tra cứu đơn & đổi/trả) |

---

*Tài liệu này là đầu ra Mốc 1 của Role 3, dùng làm căn cứ viết `REACT_SYSTEM_PROMPT` và cấu hình Guardrails (`MAX_ITERATIONS`, `TIMEOUT_SECONDS`) trong `src/prompts.py` ở Mốc 2 & Mốc 3.*

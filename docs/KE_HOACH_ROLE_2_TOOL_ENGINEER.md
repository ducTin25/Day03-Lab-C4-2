# Kế hoạch Role 2 - Tool Engineer

## Đề tài 5: Trợ lý tra cứu đơn hàng và xử lý đổi/trả

> Phạm vi phụ trách chính: `src/tools.py`  
> Mục tiêu bàn giao: bộ tool deterministic, có contract rõ ràng, xử lý lỗi an toàn, chạy độc lập không crash và được đăng ký đầy đủ trong `AVAILABLE_TOOLS`.

## 1. Căn cứ lập kế hoạch

Kế hoạch này bám theo các yêu cầu trong repo:

- Role 2 chịu trách nhiệm định nghĩa tool trong `src/tools.py`.
- Mỗi tool phải trả lời đủ 8 nội dung của Tool Contract: Name, Purpose, Input schema, Output schema, Error semantics, Side effect, Example và Safety.
- Tool phải được test độc lập trước khi nối vào ReAct Agent.
- Lỗi nghiệp vụ phải được trả về dưới dạng dữ liệu có cấu trúc, không làm ứng dụng crash.
- Tất cả tool phải được đăng ký trong `AVAILABLE_TOOLS`.
- Role 2 bàn giao tool cho Role 3 mô tả trong prompt, Role 4 tích hợp vào ReAct loop và Role 5 lấy Observation để đánh giá.

Tài liệu tham chiếu:

- [Sổ tay phân công](PHAN_CONG_CONG_VIEC.md)
- [Codelab - Thiết kế và test tool](CODELAB.md#3-thiết-kế-và-test-tool)
- [Danh sách đề tài](DANH_SACH_DE_TAI.md)

## 2. Phạm vi nghiệp vụ đề xuất

Luồng chính của trợ lý:

1. Nhận mã đơn hàng và thông tin xác minh tối thiểu.
2. Tra cứu trạng thái đơn hàng.
3. Nếu người dùng muốn đổi/trả, kiểm tra điều kiện theo từng sản phẩm.
4. Giải thích kết quả đủ điều kiện hoặc lý do bị từ chối.
5. Chỉ tạo yêu cầu đổi/trả sau khi người dùng xác nhận rõ ràng.
6. Cho phép tra cứu trạng thái xử lý của yêu cầu đổi/trả.

### Trong phạm vi MVP

- Dữ liệu giả lập cố định trong bộ nhớ để kết quả test lặp lại được.
- Tra cứu đơn theo `order_id`.
- Kiểm tra điều kiện đổi/trả theo `order_id`, `item_id` và `reason`.
- Tạo yêu cầu đổi hoặc trả hàng sau bước xác nhận.
- Tra cứu trạng thái yêu cầu đổi/trả.
- Xử lý các trường hợp sai mã đơn, sai mã sản phẩm, quá hạn, trạng thái đơn chưa giao, lý do không hợp lệ và gọi lặp.

### Ngoài phạm vi MVP

- Kết nối thật với sàn thương mại điện tử, đơn vị vận chuyển hoặc cổng thanh toán.
- Hoàn tiền thật, hủy vận đơn thật hoặc cập nhật kho thật.
- Nhận và phân tích ảnh/video sản phẩm.
- Tự quyết định ngoại lệ chính sách hoặc phê duyệt bồi thường.

## 3. Bộ tool cần xây dựng

### 3.1. `get_order_status`

**Purpose:** Tra cứu thông tin và trạng thái hiện tại của một đơn hàng. Dùng trước khi tư vấn đổi/trả. Không dùng để thay đổi đơn hàng.

**Input schema**

```python
get_order_status(order_id: str, verification_code: str) -> str
```

- `order_id`: bắt buộc, chuỗi không rỗng, ví dụ `ORD-1001`.
- `verification_code`: bắt buộc, mã xác minh giả lập; không dùng hoặc trả về PII đầy đủ.

**Output thành công:** Chuỗi JSON gồm `ok`, `code`, `message` và `data`. `data` chứa trạng thái đơn, ngày giao, danh sách sản phẩm và trạng thái thanh toán cần thiết.

**Các lỗi phải xử lý:** thiếu tham số, sai kiểu, mã đơn không tồn tại, sai mã xác minh.

**Side effect:** Không, read-only.

**Ví dụ**

```json
{
  "ok": true,
  "code": "ORDER_FOUND",
  "message": "Đã tìm thấy đơn hàng.",
  "data": {
    "order_id": "ORD-1001",
    "status": "delivered",
    "delivered_at": "2026-07-25",
    "items": [{"item_id": "ITEM-01", "name": "Áo thun", "quantity": 1}]
  }
}
```

### 3.2. `check_return_eligibility`

**Purpose:** Kiểm tra một sản phẩm có đủ điều kiện đổi/trả không và nêu rõ lý do. Chỉ dùng sau khi đã xác định đúng đơn và sản phẩm.

**Input schema**

```python
check_return_eligibility(
    order_id: str,
    item_id: str,
    reason: str,
    requested_resolution: str
) -> str
```

- `reason`: một trong `wrong_item`, `damaged`, `defective`, `not_as_described`, `changed_mind`.
- `requested_resolution`: `exchange` hoặc `refund`.

**Quy tắc giả lập tối thiểu**

- Đơn phải ở trạng thái `delivered`.
- Sản phẩm phải thuộc đơn.
- Yêu cầu nằm trong thời hạn đổi/trả đã cấu hình.
- Một số sản phẩm như hàng cá nhân hóa hoặc vệ sinh cá nhân có thể không được đổi vì thay đổi ý định.
- Yêu cầu đã tồn tại thì không tạo trùng.

**Output thành công:** Chuỗi JSON có `eligible`, `policy_code`, `reason`, `deadline` và `next_action`.

**Các lỗi phải xử lý:** đơn/sản phẩm không tồn tại, lý do không hợp lệ, hình thức xử lý không hợp lệ, thiếu ngày giao, yêu cầu đã tồn tại.

**Side effect:** Không, read-only.

### 3.3. `create_return_request`

**Purpose:** Tạo yêu cầu đổi hoặc trả hàng khi kết quả kiểm tra là đủ điều kiện và người dùng đã xác nhận.

**Input schema**

```python
create_return_request(
    order_id: str,
    item_id: str,
    reason: str,
    requested_resolution: str,
    confirmed: bool
) -> str
```

**Điều kiện bắt buộc**

- `confirmed` phải là `True`.
- Tool phải tự kiểm tra lại điều kiện đổi/trả, không chỉ tin kết quả từ LLM.
- Không tạo hai yêu cầu đang mở cho cùng `order_id` và `item_id`.

**Output thành công:** Chuỗi JSON có `request_id`, `status`, `created_at`, `resolution` và hướng dẫn bước tiếp theo.

**Các lỗi phải xử lý:** chưa xác nhận, không đủ điều kiện, yêu cầu trùng, sai tham số hoặc lỗi dữ liệu.

**Side effect:** Có, tạo bản ghi yêu cầu trong kho dữ liệu giả lập. Vì vậy tool phải yêu cầu xác nhận rõ ràng và có cơ chế chống gọi lặp.

**Nguyên tắc an toàn:** Không giả vờ đã hoàn tiền hoặc đã đổi hàng. Chỉ thông báo “đã tạo yêu cầu” và trạng thái ban đầu.

### 3.4. `get_return_request_status`

**Purpose:** Tra cứu tiến độ của một yêu cầu đổi/trả đã tạo.

**Input schema**

```python
get_return_request_status(request_id: str, verification_code: str) -> str
```

**Output thành công:** Chuỗi JSON có `request_id`, `status`, `resolution`, `updated_at` và `next_action`.

**Các lỗi phải xử lý:** mã yêu cầu không tồn tại, sai mã xác minh, thiếu tham số.

**Side effect:** Không, read-only.

## 4. Chuẩn chung khi implement

### 4.1. Cấu trúc phản hồi

Tất cả tool trả về chuỗi JSON theo một envelope thống nhất:

```json
{
  "ok": false,
  "code": "ORDER_NOT_FOUND",
  "message": "Không tìm thấy đơn hàng.",
  "data": null
}
```

Quy ước:

- `ok`: kết quả kỹ thuật/nghiệp vụ của lời gọi.
- `code`: mã ổn định để Agent và test nhận diện.
- `message`: câu tiếng Việt dễ hiểu, không lộ dữ liệu nhạy cảm.
- `data`: dữ liệu chi tiết khi cần; dùng `null` nếu thất bại.

### 4.2. Danh sách mã lỗi tối thiểu

- `INVALID_INPUT`
- `ORDER_NOT_FOUND`
- `VERIFICATION_FAILED`
- `ITEM_NOT_FOUND`
- `ORDER_NOT_DELIVERED`
- `RETURN_WINDOW_EXPIRED`
- `ITEM_NOT_RETURNABLE`
- `INVALID_REASON`
- `INVALID_RESOLUTION`
- `CONFIRMATION_REQUIRED`
- `DUPLICATE_REQUEST`
- `RETURN_REQUEST_NOT_FOUND`
- `INTERNAL_TOOL_ERROR`

### 4.3. Quy tắc code

- Validate kiểu dữ liệu, chuỗi rỗng và giá trị enum ở đầu mỗi hàm.
- Không để `.strip()`, `.lower()` hoặc truy cập dictionary gây exception khi input là `None` hay sai kiểu.
- Bao lỗi không dự kiến bằng `try/except` và trả `INTERNAL_TOOL_ERROR`; không trả stack trace cho người dùng.
- Không ghi API key, địa chỉ, số điện thoại hoặc mã xác minh vào log.
- Dữ liệu mock và thời gian tham chiếu phải cố định để test deterministic.
- Docstring của từng tool phải ghi rõ Purpose, Args, Returns, Errors, Side effects và Example.
- Đăng ký đúng tên hàm trong `AVAILABLE_TOOLS`.
- Không sửa `src/app.py`, `src/prompts.py` hoặc `config/test_cases.json` nếu chưa thống nhất với role sở hữu file.

## 5. Kế hoạch thực hiện theo 4 mốc của lab

### Mốc 1 - Định hình tool (ước tính 10-15 phút)

- [ ] Đọc test case dự kiến của Role 1 và chốt các luồng nghiệp vụ.
- [ ] Thống nhất 4 tool MVP và tên tham số với Role 3, Role 4.
- [ ] Chốt dữ liệu mock: ít nhất 3 đơn hàng và 3 trạng thái khác nhau.
- [ ] Chốt quy tắc đổi/trả giả lập, thời hạn và danh sách lý do.
- [ ] Ghi lại các failure mode để Role 3 đưa vào prompt/guardrail.

**Đầu ra:** danh sách tool, schema sơ bộ, quy tắc nghiệp vụ và failure mode.

### Mốc 2 - Viết Tool Specs và code nền (ước tính 30-40 phút)

- [ ] Thay bộ tool thời tiết/chuyến bay mẫu trong `src/tools.py` bằng tool của đề tài.
- [ ] Tạo dữ liệu `MOCK_ORDERS` và `MOCK_RETURN_REQUESTS`.
- [ ] Tạo helper nội bộ cho response JSON, validate input và kiểm tra chính sách.
- [ ] Implement `get_order_status`.
- [ ] Implement `check_return_eligibility`.
- [ ] Viết docstring đầy đủ theo 8 câu hỏi Tool Contract.
- [ ] Chạy thử từng hàm độc lập với input đúng và sai.

**Đầu ra:** hai tool read-only hoạt động ổn định và contract đã chốt.

### Mốc 3 - Tool thay đổi trạng thái và khả năng chịu lỗi (ước tính 35-45 phút)

- [ ] Implement `create_return_request` với `confirmed`.
- [ ] Implement `get_return_request_status`.
- [ ] Thêm chống tạo yêu cầu trùng.
- [ ] Bắt toàn bộ lỗi nghiệp vụ bằng mã lỗi, không crash.
- [ ] Đăng ký 4 tool trong `AVAILABLE_TOOLS`.
- [ ] Gửi tên tool, schema và output mẫu cho Role 3 cập nhật prompt.
- [ ] Gửi registry và ví dụ gọi hàm cho Role 4 tích hợp executor.
- [ ] Hỗ trợ Role 4 chạy trace có ít nhất hai bước: tra đơn -> kiểm tra điều kiện -> tạo yêu cầu.

**Đầu ra:** bộ tool hoàn chỉnh, có read-only và side effect an toàn.

### Mốc 4 - Cross-audit và hoàn thiện (ước tính 20-30 phút)

- [ ] Chạy các câu bẫy từ nhóm khác.
- [ ] Bổ sung validation cho các input chưa lường trước.
- [ ] Kiểm tra thông báo lỗi đủ rõ để Agent chuyển hướng hoặc dừng lịch sự.
- [ ] Kiểm tra không rò rỉ mã xác minh/PII trong Observation.
- [ ] Gửi trace lỗi tiêu biểu và mã lỗi cho Role 5.
- [ ] Rà lại docstring, registry và checklist Definition of Done.

**Đầu ra:** bản `src/tools.py` sẵn sàng nghiệm thu và bàn giao.

## 6. Dữ liệu mock tối thiểu

Nên có các bản ghi sau để bao phủ các nhánh quan trọng:

| Mã đơn | Trạng thái | Trường hợp cần kiểm tra |
| --- | --- | --- |
| `ORD-1001` | `delivered` | Còn hạn, sản phẩm được phép đổi/trả |
| `ORD-1002` | `shipping` | Chưa giao nên chưa được tạo yêu cầu |
| `ORD-1003` | `delivered` | Quá hạn đổi/trả |
| `ORD-1004` | `delivered` | Có sản phẩm thuộc nhóm không đổi vì thay đổi ý định |

Mỗi đơn cần tối thiểu: `order_id`, mã xác minh giả lập, `status`, `delivered_at`, danh sách `items` và các thuộc tính chính sách cần thiết.

## 7. Kế hoạch test độc lập cho Role 2

| ID | Tool | Tình huống | Kết quả mong đợi |
| --- | --- | --- | --- |
| T01 | `get_order_status` | Đơn tồn tại, xác minh đúng | `ok=true`, `ORDER_FOUND` |
| T02 | `get_order_status` | Mã đơn không tồn tại | `ok=false`, `ORDER_NOT_FOUND` |
| T03 | `get_order_status` | Sai mã xác minh | `VERIFICATION_FAILED`, không lộ dữ liệu đơn |
| T04 | `get_order_status` | `None`, số hoặc chuỗi rỗng | `INVALID_INPUT`, không exception |
| T05 | `check_return_eligibility` | Đã giao, còn hạn | `eligible=true` |
| T06 | `check_return_eligibility` | Đơn đang vận chuyển | `ORDER_NOT_DELIVERED` |
| T07 | `check_return_eligibility` | Quá hạn | `RETURN_WINDOW_EXPIRED` |
| T08 | `check_return_eligibility` | `item_id` không thuộc đơn | `ITEM_NOT_FOUND` |
| T09 | `check_return_eligibility` | Lý do/hình thức sai enum | `INVALID_REASON` hoặc `INVALID_RESOLUTION` |
| T10 | `create_return_request` | `confirmed=false` | `CONFIRMATION_REQUIRED`, không tạo dữ liệu |
| T11 | `create_return_request` | Đủ điều kiện và đã xác nhận | Tạo `request_id`, trạng thái `pending` |
| T12 | `create_return_request` | Gọi lại cùng đơn/sản phẩm | `DUPLICATE_REQUEST`, không tạo bản ghi thứ hai |
| T13 | `create_return_request` | Sản phẩm không đủ điều kiện | Không tạo dữ liệu, trả đúng mã chính sách |
| T14 | `get_return_request_status` | Mã yêu cầu hợp lệ | Trả đúng trạng thái và bước tiếp theo |
| T15 | `get_return_request_status` | Mã yêu cầu sai | `RETURN_REQUEST_NOT_FOUND` |

Điều kiện pass: 100% test trên chạy xong, không có exception thoát ra ngoài tool.

## 8. Phối hợp với các role khác

### Bàn giao cho Role 1

- Danh sách trạng thái đơn, lý do đổi/trả và mã lỗi để viết test case đúng khả năng tool.
- Đề nghị test case có đủ: câu đơn giản, một tool, nhiều tool và edge case.

### Bàn giao cho Role 3

- Tên tool chính xác, thứ tự tham số, enum hợp lệ và ví dụ Action.
- Quy tắc bắt buộc hỏi xác nhận trước `create_return_request`.
- Hướng xử lý khi nhận `ok=false`: không bịa dữ liệu, không gọi lặp vô hạn, giải thích lịch sự.

### Bàn giao cho Role 4

- `AVAILABLE_TOOLS` đã cập nhật.
- Cách parse nhiều tham số, bao gồm boolean `confirmed`.
- Lưu ý tool tạo yêu cầu có side effect và cần chống executor gọi lại ngoài ý muốn.
- Ví dụ chuỗi gọi mong đợi:

```text
get_order_status["ORD-1001", "VC-01"]
check_return_eligibility["ORD-1001", "ITEM-01", "damaged", "exchange"]
create_return_request["ORD-1001", "ITEM-01", "damaged", "exchange", true]
```

### Bàn giao cho Role 5

- Output mẫu thành công/thất bại để ghi Observation.
- Trace chứng minh tool selection, grounding và termination.
- Một trace side effect bị chặn vì chưa xác nhận và một trace tạo yêu cầu thành công.

## 9. Definition of Done

- [ ] `src/tools.py` chỉ chứa tool đúng với đề tài số 5, không còn tool mẫu thời tiết/chuyến bay.
- [ ] Có đủ 4 tool MVP và tất cả nằm trong `AVAILABLE_TOOLS`.
- [ ] Mỗi tool có docstring đầy đủ về input, output, error và side effect.
- [ ] Tất cả phản hồi theo cùng một cấu trúc JSON string.
- [ ] Input sai, mã không tồn tại và lỗi nghiệp vụ đều không làm chương trình crash.
- [ ] Tool tạo yêu cầu bắt buộc xác nhận và chống tạo trùng.
- [ ] Không có thao tác hoàn tiền/đổi hàng thật hoặc thông báo sai rằng thao tác thật đã hoàn tất.
- [ ] Không lộ mã xác minh hoặc PII trong response/log.
- [ ] 15 test độc lập đạt 100%.
- [ ] Role 3 và Role 4 xác nhận đã nhận đúng contract.
- [ ] Role 5 có ít nhất một Observation thành công và một Observation lỗi để đưa vào báo cáo.

## 10. Rủi ro và cách giảm thiểu

| Rủi ro | Cách giảm thiểu |
| --- | --- |
| Role 1 đổi test case sau khi tool đã hoàn thành | Chốt enum, schema và dữ liệu mock ngay ở Mốc 1 |
| Prompt gọi sai tên hoặc sai thứ tự tham số | Gửi contract và Action mẫu cho Role 3 |
| Executor của Role 4 chưa parse boolean/nhiều tham số | Kiểm tra sớm bằng một trace tích hợp tối thiểu |
| Agent gọi tool tạo yêu cầu nhiều lần | Dùng `confirmed` và kiểm tra duplicate trong chính tool |
| Ngày hiện tại làm test lúc pass lúc fail | Dùng ngày tham chiếu cố định hoặc truyền clock test được kiểm soát |
| Exception kỹ thuật làm dừng ReAct loop | Validate sớm, bắt exception và trả `INTERNAL_TOOL_ERROR` |
| Observation lộ thông tin khách hàng | Chỉ trả dữ liệu tối thiểu, che PII và không log mã xác minh |

## 11. Thứ tự ưu tiên nếu thiếu thời gian

1. Hoàn thành `get_order_status` và `check_return_eligibility`.
2. Chuẩn hóa response/error và bảo đảm không crash.
3. Hoàn thành `create_return_request` có xác nhận và chống trùng.
4. Hoàn thành `get_return_request_status`.
5. Mở rộng thêm dữ liệu mock và edge case.


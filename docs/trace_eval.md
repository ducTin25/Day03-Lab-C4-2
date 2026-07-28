# 📊 BÁO CÁO GIÁM SÁT & ĐÁNH GIÁ (OBSERVABILITY TRACE LOGS)
*Dành cho Role 5: Observability & Reviewer*

---

## 🎯 1. BẢNG CHẤM ĐIỂM AGENTIC FIT (SCORING MATRIX)

| Tiêu chí | Điểm (1-5) | Lý do đánh giá |
| :--- |:----------:| :--- |
| 🧠 **Multi-step Reasoning** |   `4/5`    | Cần hiểu yêu cầu, xác định đơn hàng, kiểm tra trạng thái và đối chiếu chính sách đổi trả. |
| 🛠️ **Tool Interaction** |   `5/5`    | Cần tương tác với hệ thống đơn hàng, vận chuyển, tồn kho, thanh toán và tạo yêu cầu đổi trả. |
| 🔀 **Dynamic Decision** |   `5/5`    | Kết quả tra cứu quyết định bước tiếp theo: thông báo trạng thái, tạo yêu cầu đổi trả hoặc chuyển nhân viên hỗ trợ. |
| ⏳ **Long Horizon** |   `3/5`    | Một yêu cầu thường gồm 3–5 bước, nhưng phần lớn được hoàn thành trong một phiên hội thoại. |
| **TỔNG ĐIỂM FIT** | **17/20**  | **KẾT LUẬN: BÀI TOÁN RẤT NÊN DÙNG REACT AGENT!** |

---

## 🔍 2. SO SÁNH PHẢN HỒI (TEST CASE #3)

**Câu hỏi**: *" Kiểm tra giúp tôi trạng thái đơn hàng ORD-1001. Mã xác minh của tôi là VC-01"*

### 🤖 Chatbot Baseline:
* **Phản hồi**: *Chào bạn, cảm ơn bạn đã liên hệ.

Rất tiếc, ở chế độ hiện tại (Baseline - Mốc 2) mình chưa được cấp quyền truy xuất dữ liệu đơn hàng thực tế, vì vậy mình không thể tra cứu trạng thái cụ thể của đơn **ORD-1001** với mã xác minh **VC-01** được ạ.

Tính năng tra cứu trạng thái đơn hàng và xử lý yêu cầu đổi/trả sẽ hoạt động đầy đủ ở phiên bản **ReAct Agent (Mốc 3)**. Bạn vui lòng quay lại sau khi phiên bản này được nâng cấp nhé!"*
* **Nhận xét**: Chatbot phản hồi an toàn, minh bạch và không tự tạo trạng thái đơn hàng khi chưa có quyền truy cập dữ liệu.

### 🧠 ReAct Agent:
* **Thought 1**: Người dùng muốn kiểm tra trạng thái đơn hàng ORD-1001 với mã xác minh VC-01. Tôi sẽ sử dụng công cụ get_order_status.
* **Action 1**: `get_order_status[ORD-1001, VC-01]`
* **Observation 1**: ` {"code": "ORDER_FOUND", "data": {"delivered_at": "2026-07-25", "items": [{"item_id": "ITEM-01", "name": "Áo thun Basic", "quantity": 1}, {"item_id": "ITEM-02", "name": "Bình nước cá nhân", "quantity": 1}], "order_id": "ORD-1001", "ordered_at": "2026-07-22", "payment_status": "paid", "status": "delivered"}, "message": "Đã tìm thấy đơn hàng.", "ok": true}`
* **Thought 2**:  Tôi đã có đủ thông tin để trả lời.
* **Final Answer**: *"Đơn hàng **ORD-1001** của bạn đã được giao thành công vào ngày **25/07/2026**. Trạng thái hiện tại là **delivered** và thanh toán đã hoàn tất. Các sản phẩm trong đơn gồm:

1. **Áo thun Basic** (1 cái) - Mã ITEM-01
2. **Bình nước cá nhân** (1 cái) - Mã ITEM-02

Bạn cần hỗ trợ thêm về đổi trả hay kiểm tra sản phẩm nào không?"*
* **Nhận xét**: Hoàn thành xuất sắc nhiệm vụ nhờ sự kết hợp giữa suy luận và công cụ.

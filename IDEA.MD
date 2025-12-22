Bản thiết kế chi tiết (Technical Blueprint) cho hệ thống Bot Điểm Danh Telegram của bạn.
1. Kiến trúc Hệ thống (System Architecture)
Hệ thống hoạt động theo mô hình Client-Server đơn giản nhưng bảo mật:

Client (Người dùng): App Telegram trên điện thoại (Android/iOS).

Interface (Giao tiếp): Telegram Bot API.

Backend (Xử lý): Python Script (chạy 24/7 trên VPS hoặc máy chủ cá nhân).

Database (Lưu trữ): SQLite (cho quy mô nhỏ < 500 người) hoặc PostgreSQL (quy mô lớn).

Reporting (Báo cáo): Xuất file Excel (.xlsx) gửi trực tiếp qua chat hoặc đồng bộ lên Google Sheets.
2. Luồng dữ liệu & Quy trình (User Flow)
Chúng ta chia làm 3 giai đoạn chính để đảm bảo "quản lý số lượng chính xác nhất".

Giai đoạn 1: Onboarding (Thiết lập & Đăng ký)
Để tránh người lạ spam hoặc vào điểm danh bậy:

User: Bấm /start -> Bot yêu cầu nhập Họ và Tên thật.

Bot: Lưu thông tin vào trạng thái PENDING (Chờ duyệt).

Admin: Nhận thông báo "Có thành viên mới xin gia nhập: Nguyễn Văn A".

Admin: Gõ lệnh /approve [ID] -> User chính thức được phép sử dụng Bot.

Mục đích: Đảm bảo danh sách nhân sự là thật 100%.
Giai đoạn 2: Admin Setup (Cấu hình địa điểm)
Admin cần cài đặt "Vùng an toàn" (Geofence):
Admin: Đến văn phòng, gửi vị trí hiện tại cho Bot.
Bot: Hỏi "Đây là vị trí văn phòng? Nhập bán kính cho phép (mét)".
Admin: Nhập 50 (tức là cho phép sai số 50m).
Bot: Lưu tọa độ trung tâm $O(lat, long)$ và bán kính $R$.
Giai đoạn 3: Điểm danh (Daily Workflow)
User: Nhấn nút "📍 Check-in" trên menu.

Bot: Kiểm tra giờ. Nếu quá muộn (ví dụ sau 9:00 AM), cảnh báo "Bạn đang đi muộn".

User: Gửi Location (Live hoặc Current Location).
Bot (Xử lý ngầm):

Kiểm tra message.forward_date: Nếu có -> Từ chối (đây là tin nhắn forward từ hôm khác).
Tính khoảng cách $d$ từ User đến $O$.
Nếu $d \le R$: Thành công -> Ghi vào DB -> Trả lời "Check-in thành công lúc 08:00 tại Văn phòng".
Nếu $d > R$: Thất bại -> Trả lời "Bạn đang cách văn phòng 200m. Vui lòng di chuyển lại gần".
3. Thiết kế Cơ sở dữ liệu (Database Schema)
Để quản lý chặt chẽ, bạn cần cấu trúc dữ liệu như sau (Ví dụ dùng SQL):
Bảng 1: users (Quản lý nhân sự)Tên trườngKiểu dữ liệuMô tảuser_idINTEGER (PK)ID Telegram (Duy nhất)full_nameTEXTTên thật nhân viênroleTEXT'admin' hoặc 'member'statusTEXT'active', 'pending', 'banned'joined_atDATETIMENgày gia nhập
Bảng 2: locations (Cấu hình địa điểm - hỗ trợ nhiều chi nhánh)Tên trườngKiểu dữ liệuMô tảidINTEGER (PK)ID địa điểmnameTEXTTên (Vd: VP Hà Nội)latitudeFLOATVĩ độ gốclongitudeFLOATKinh độ gốcradiusINTEGERBán kính cho phép (mét)
Bảng 3: attendance_logs (Nhật ký chi tiết)Tên trườngKiểu dữ liệuMô tảidINTEGER (PK)ID loguser_idINTEGER (FK)Link tới bảng userstypeTEXT'IN' (đến) hoặc 'OUT' (về)timestampDATETIMEThời gian thực serverdistanceFLOATKhoảng cách đo được (để hậu kiểm)is_lateBOOLEANTrue nếu đi muộn
4. Các chức năng dành cho Admin (Admin Commands)
Để bạn quản lý số lượng chính xác nhất, Bot sẽ có bộ lệnh riêng cho Admin:

/set_location: Đặt vị trí văn phòng tại chỗ Admin đang đứng.

/list_users: Xem danh sách toàn bộ nhân viên và trạng thái (Active/Pending).

/today: Xem nhanh ai đã đến, ai chưa đến, ai đi muộn trong ngày hôm nay.

/export_excel [tháng]: Bot sẽ gửi lại file .xlsx chứa bảng công chi tiết của tháng đó (Có các cột: Ngày, Tên, Giờ vào, Giờ ra, Số phút muộn, Ghi chú).

/broadcast [tin nhắn]: Gửi thông báo đến tất cả nhân viên (Ví dụ: "Hôm nay họp lúc 10h").
5. Giải pháp Kỹ thuật Chống Gian Lận (Anti-Cheat Security)
Đây là phần cốt lõi để đảm bảo độ chính xác:

Check Forward: Telegram API có thuộc tính forward_from. Nếu tin nhắn Location có thuộc tính này -> Block ngay (vì user lấy tin nhắn cũ forward lại).

Check Live Time: So sánh message.date với server_time. Nếu chênh lệch quá 60 giây -> Từ chối (User đang tắt mạng hoặc dùng tool gửi lại packet cũ).

Check Device: Telegram không cung cấp thông tin thiết bị (PC/Mobile), nhưng tính năng request_location chỉ hoạt động tốt trên Mobile. Trên PC user không gửi được GPS chính xác -> Hạn chế được việc check-in từ máy tính ở nhà.
# 07. SECURITY & PERFORMANCE REQUIREMENTS

> **Tài liệu:** Đặc tả Bảo mật, Phân quyền, Giới hạn Tải (Rate Limiting), Bảo vệ Dữ liệu và Hiệu năng  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)  
> **Đối chiếu:** `app/core/security.py`, `app/core/deps.py`, `app/routers/*.py`, `supabase/migrations/0001_init.sql`

---

## 1. Bảo mật Xác thực (Authentication Security)

| Mã yêu cầu | Hạng mục | Hiện trạng trong Code | Đánh giá | Yêu cầu Hoàn thiện / Tiêu chí Nghiệm thu |
| :--- | :--- | :--- | :---: | :--- |
| **SEC-AUTH-01** | Băm mật khẩu (Password Hashing) | Sử dụng `pwdlib.PasswordHash.recommended()` (thuật toán **Argon2id**). | `VERIFIED` | Không bao giờ lưu mật khẩu dạng rõ hoặc dùng MD5/SHA1/SHA256 đơn thuần cho mật khẩu. |
| **SEC-AUTH-02** | Tách biệt loại JWT Token (`typ`) | Payload JWT có trường `"typ": "access"` hoặc `"typ": "refresh"`. Hàm `_user_from_token` từ chối token nếu `typ != "access"`. | `VERIFIED` | Đảm bảo kẻ tấn công không thể dùng `refresh_token` làm Bearer token để gọi API nghiệp vụ. |
| **SEC-AUTH-03** | Lưu trữ Refresh Token an toàn | Chỉ lưu mã băm `SHA-256(jti)` vào cột `refresh_tokens.token_hash` (64 ký tự hex), không lưu chuỗi JWT gốc. | `VERIFIED` | Ngay cả khi lộ dữ liệu bảng `refresh_tokens`, kẻ tấn công không thể tái tạo JWT Refresh Token hợp lệ vì không có `jti` gốc và `JWT_SECRET`. |
| **SEC-AUTH-04** | Xoay vòng Refresh Token (Token Rotation) | Mỗi lần gọi `/v1/auth/refresh`, bản ghi token cũ được gán `revoked_at = now` và cấp token mới. | `VERIFIED` | Dùng lại refresh token đã qua sử dụng trả về ngay `401 Unauthorized` (kiểm chứng qua `test_register_refresh_rotation`). |
| **SEC-AUTH-05** | Kiểm tra độ mạnh của `JWT_SECRET` | Trong `app/core/config.py`, giá trị mặc định đang là `"dev-only-change-me"`. | `PARTIAL` | Khi chạy ở môi trường `APP_ENV=production`, hệ thống phải cảnh báo hoặc từ chối khởi động nếu `JWT_SECRET` vẫn mang giá trị mặc định hoặc ngắn hơn 32 ký tự. |
| **SEC-AUTH-06** | Tự động tạo tài khoản Demo | Trong `app/seed.py`, khi `AUTO_SEED=true`, hệ thống tự tạo tài khoản `demo@ngonsacviet.example.com` với `role="reviewer"` và mật khẩu mặc định `"Demo1234"`. | `BUG` / `RISK` | **Rủi ro bảo mật nghiêm trọng trên Production**: Nếu bật `AUTO_SEED=true` trên môi trường thật mà không đổi `DEMO_PASSWORD`, bất kỳ ai cũng có thể đăng nhập quyền `reviewer` để duyệt câu và tải dữ liệu. Cần tách cờ `SEED_DEMO_USER` (mặc định `False` trên production) hoặc yêu cầu mật khẩu mạnh. |

---

## 2. Phân quyền Truy cập (Authorization & RBAC)

### 2.1. Ma trận Phân quyền theo Vai trò (Role Matrix)

| Nhóm API / Thao tác | Guest (Chưa đăng nhập) | `member` | `reviewer` | `admin` | Hiện trạng Code |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Xem Ngôn ngữ, Dân tộc, Di sản, Bài học | Cho phép | Cho phép | Cho phép | Cho phép | `VERIFIED` |
| Dịch văn bản, OCR ảnh, ASR giọng nói | Cho phép | Cho phép (Lưu `user_id`) | Cho phép (Lưu `user_id`) | Cho phép (Lưu `user_id`) | `VERIFIED` |
| Làm bài Quiz (`/v1/lessons/{id}/quiz`) | Cho phép | Cho phép (Lưu tiến độ) | Cho phép (Lưu tiến độ) | Cho phép (Lưu tiến độ) | `PARTIAL` |
| Gửi đóng góp, Sync Push, Xem đóng góp cá nhân | Chặn (`401`) | Cho phép | Cho phép | Cho phép | `VERIFIED` |
| Xem hàng đợi kiểm duyệt (`GET /v1/contributions`) | Chặn (`401`) | Chặn (`403`) | Cho phép | Cho phép | `PARTIAL` (Đang chặn `admin`) |
| Duyệt / Từ chối đóng góp (`POST .../review`) | Chặn (`401`) | Chặn (`403`) | Cho phép (Trừ bài tự gửi) | Cho phép | `PARTIAL` (Chưa chặn tự duyệt) |
| Xuất CSV huấn luyện (`GET /v1/training/pairs.csv`) | Chặn (`401`) | Chặn (`403`) | Cho phép | Cho phép | `PARTIAL` (Đang chặn `admin`) |

### 2.2. Các Quy tắc Phân quyền Cần Khắc phục
1. **SEC-RBAC-01 (Hỗ trợ vai trò `admin`)**: Cập nhật hàm `_reviewer(user)` trong `app/routers/community.py` để chấp nhận `user.role in ("reviewer", "admin")`.
2. **SEC-RBAC-02 (Chống xung đột lợi ích khi duyệt bài)**: Người dùng có `role == "reviewer"` không được tự phê duyệt đóng góp do chính mình gửi (`row.user_id == user.id`), trừ trường hợp tài khoản có `role == "admin"` hoặc cấu hình cho phép trong môi trường kiểm thử/demo.

---

## 3. Bảo vệ Dữ liệu & Kiểm soát Tệp Tải lên (Data & Upload Security)

| Mã yêu cầu | Mô tả | Hiện trạng | Giải pháp kỹ thuật |
| :--- | :--- | :---: | :--- |
| **SEC-DATA-01** | Chống SQL Injection | `VERIFIED` | Toàn bộ truy vấn sử dụng SQLAlchemy 2.0 ORM (`select()`, `where()`) với tham số hóa hoàn toàn, không nối chuỗi SQL thủ công. |
| **SEC-DATA-02** | Bảo vệ đáp án Quiz (`is_correct`) | `VERIFIED` | Hàm `_lesson` trong `app/routers/learn.py` chỉ trích xuất `id`, `text_vi`, `text_en` của `QuizChoice`; trên PostgreSQL có thêm view `quiz_choices_public` và RLS chặn truy cập bảng `quiz_choices`. |
| **SEC-DATA-03** | Bảo vệ quyền riêng tư khi xuất CSV | `VERIFIED` | Endpoint `/v1/training/pairs.csv` chỉ xuất 5 cột: `source_lang,target_lang,source,target,verified`, không lộ `user_id`, `email` hay `client_id`. |
| **SEC-UP-01** | Giới hạn dung lượng tệp tải lên | `VERIFIED` | Đọc luồng có giới hạn `file.read(MAX_BYTES + 1)`: Ảnh tối đa **8 MB**, Audio tối đa **20 MB**. Vượt ngưỡng trả về `413 Payload Too Large`. |
| **SEC-UP-02** | Kiểm tra tệp rỗng & định dạng MIME/Extension | `PARTIAL` | Hiện tại `translate_image` và `translate_speech` chưa chặn tệp 0 byte hoặc tệp thực thi giả dạng. Cần bổ sung kiểm tra tệp không rỗng (`len(content) > 0`) và kiểm tra `content_type` / phần mở rộng hợp lệ (`image/*` cho OCR; `audio/*`, `video/mp4`, `application/octet-stream` cho ASR). |
| **SEC-RATE-01** | Giới hạn tần suất gọi API (Rate Limiting) | `MISSING` | Cần bổ sung cơ chế Rate Limiting nhẹ trong bộ nhớ (In-memory sliding window theo IP/User) cho các endpoint nhạy cảm: `/v1/auth/login`, `/v1/auth/register` và `/v1/translate*` (có thể bật/tắt qua biến môi trường để không ảnh hưởng tới pytest). |

---

## 4. Yêu cầu Hiệu năng, Logging & Giám sát (Performance & Monitoring)

### 4.1. Hiệu năng Truy vấn Cơ sở Dữ liệu
- **Chống lỗi N+1 Query (`VERIFIED`)**:
  - `app/routers/catalog.py`: Đã sử dụng `selectinload(EthnicGroup.heritage)` khi lấy chi tiết dân tộc.
  - `app/routers/learn.py`: Đã sử dụng `selectinload(Lesson.phrases)` và `selectinload(Lesson.questions).selectinload(QuizQuestion.choices)`.
  - `app/routers/community.py`: Đã sử dụng `selectinload` đầy đủ trong `/v1/sync/pull`.
- **Connection Pooling (`PARTIAL`)**:
  - Trên SQLite dùng `StaticPool`.
  - Trên PostgreSQL (`asyncpg`), cần cho phép cấu hình `pool_size` (mặc định 5–10), `max_overflow` (10) và `pool_pre_ping=True` trong `make_engine()` để tự động phục hồi kết nối khi AWS RDS khởi động lại hoặc ngắt kết nối nhàn rỗi.

### 4.2. Logging & Bảo mật Nhật ký Hệ thống
- **Không ghi thông tin nhạy cảm (`SEC-LOG-01`)**: Tuyệt đối không ghi `password`, `access_token`, `refresh_token`, `JWT_SECRET`, hoặc chuỗi kết nối `DATABASE_URL` có chứa mật khẩu ra console/log file.
- **Giám sát thời gian xử lý (`PERF-LOG-01`)**: Ghi nhận thời gian phản hồi khi gọi ML Service (`translate`, `ocr`, `asr`) và trạng thái kiểm tra kết nối DB tại endpoint `/health`.


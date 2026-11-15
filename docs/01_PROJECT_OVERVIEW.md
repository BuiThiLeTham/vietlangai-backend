# 01. PROJECT OVERVIEW – NGÔN SẮC VIỆT (VIETLANGAI)

> **Tài liệu:** Tổng quan Dự án & Phạm vi Backend  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)  
> **Trạng thái kiểm tra:** Đối chiếu trực tiếp với mã nguồn `vietlangai-backend` (commit `6e02db9`)

---

## 1. Tổng quan dự án Ngôn Sắc Việt

**Ngôn Sắc Việt (VietLangAI)** là nền tảng ứng dụng Trí tuệ Nhân tạo (AI) kết hợp lưu trữ học liệu số nhằm bảo tồn, tra cứu, học tập và phát huy ngôn ngữ, chữ viết cũng như di sản văn hóa của các dân tộc thiểu số tại Việt Nam.

Trong giai đoạn hiện tại, hệ thống tập trung vào **5 dân tộc thiểu số** và **7 ngôn ngữ** (bao gồm 5 ngôn ngữ dân tộc và 2 ngôn ngữ cầu nối/pivot):

| Mã ngôn ngữ (`code`) | ISO 639-3 | Tên tiếng Việt | Tên tiếng Anh | Hệ chữ viết (`script`) | Ngữ hệ (`family`) | Vai trò (`role`) | Tier đánh giá | Dân tộc liên kết (`slug`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `vi` | `vie` | Tiếng Việt | Vietnamese | `Latn` | Austroasiatic, Vietic | `pivot` | 0 | *(Ngôn ngữ cầu nối)* |
| `en` | `eng` | Tiếng Anh | English | `Latn` | Indo-European, Germanic | `pivot` | 0 | *(Ngôn ngữ cầu nối)* |
| `tyz` | `tyz` | Tiếng Tày | Tay | `Latn` | Tai-Kadai | `ethnic` | 1 | `tay` (Người Tày) |
| `rad` | `rad` | Tiếng Ê Đê | Rade (Ede) | `Latn` | Austronesian, Chamic | `ethnic` | 1 | `ede` (Người Ê Đê) |
| `cjm` | `cjm` | Tiếng Chăm | Eastern Cham | `Cham` | Austronesian, Chamic | `ethnic` | 1 | `cham` (Người Chăm) |
| `hmn` | `hmn` | Tiếng H'Mông | Hmong | `Latn` | Hmong-Mien | `ethnic` | 2 | `hmong` (Người H'Mông) |
| `jra` | `jra` | Tiếng Jrai | Jarai | `Latn` | Austronesian, Chamic | `ethnic` | 2 | `jrai` (Người Jrai) |

---

## 2. Mục tiêu và Phạm vi Backend

### 2.1. Mục tiêu cốt lõi
1. **Cung cấp RESTful API tập trung (`/v1/...`)** cho ứng dụng di động Flutter (`vietlangai-mob`) và các công cụ quản trị/kiểm duyệt dữ liệu.
2. **Điều phối dịch thuật AI đa phương thức (Text, Image OCR, Voice ASR)** thông qua kết nối HTTP bất đồng bộ tới dịch vụ ML độc lập (`ML Service`), đồng thời lưu vết lịch sử dịch thuật (`translation_logs`).
3. **Bảo vệ tính xác thực của học liệu và ngữ liệu văn hóa**: Chỉ hiển thị các câu mẫu đã xác minh (`verified = true`), ẩn đáp án trắc nghiệm (`is_correct`) khỏi phía client trước khi nộp bài, và yêu cầu quy trình kiểm duyệt (`pending` -> `approved` / `rejected`) đối với mọi câu đóng góp từ cộng đồng trước khi xuất thành dữ liệu huấn luyện AI (`/v1/training/pairs.csv`).
4. **Hỗ trợ hoạt động ngoại tuyến (Offline-first)**: Cho phép thiết bị di động tải gói dữ liệu danh mục & bài học về máy (`GET /v1/sync/pull`) và đẩy hàng loạt câu đóng góp đã lưu cục bộ lên server khi có mạng (`POST /v1/sync/push`) với cơ chế chống trùng lặp qua `client_id`.
5. **Sẵn sàng triển khai đám mây (Cloud-ready)**: Tương thích với PostgreSQL (AWS RDS PostgreSQL / Supabase PostgreSQL) và hỗ trợ chạy độc lập với SQLite trong môi trường phát triển/kiểm thử cục bộ.

### 2.2. Phạm vi trách nhiệm của Backend
- **Thuộc phạm vi Backend**:
  - Xác thực (JWT Access Token + Refresh Token Rotation) và phân quyền theo vai trò (`role`).
  - Quản lý danh mục ngôn ngữ, dân tộc, di sản văn hóa.
  - Quản lý bài học, câu/từ vựng mẫu (`phrases`), câu hỏi trắc nghiệm và chấm điểm (`scoring`).
  - Tích hợp với ML Service qua lớp client độc lập (`app/integrations/ml_client.py`).
  - Tiếp nhận, đồng bộ, kiểm duyệt dữ liệu cộng đồng và xuất CSV phục vụ huấn luyện mô hình.
  - Quản lý schema cơ sở dữ liệu, migrations, seeding dữ liệu gốc từ `shared/languages.json`.
- **Ngoài phạm vi Backend**:
  - Mã nguồn giao diện người dùng Flutter (`vietlangai-mob`).
  - Quá trình huấn luyện (training/fine-tuning) trực tiếp mô hình NLLB/Whisper/OCR (được thực hiện ở nhánh ML riêng).

---

## 3. Các nhóm người dùng và vai trò (User Roles)

Dựa trên mã nguồn hiện tại (`app/models.py`, `app/core/deps.py`, `app/routers/community.py`) và yêu cầu mở rộng của hệ thống:

| Nhóm người dùng | Giá trị `User.role` | Trạng thái trong Code | Quyền hạn và chức năng |
| :--- | :--- | :---: | :--- |
| **Khách (Anonymous / Guest)** | *(Không cần đăng nhập)* | `VERIFIED` | - Xem danh sách ngôn ngữ (`GET /v1/languages`), dân tộc (`GET /v1/peoples`), chi tiết dân tộc & di sản (`GET /v1/peoples/{slug}`).<br>- Xem danh sách bài học (`GET /v1/lessons`), chi tiết bài học (`GET /v1/lessons/{id}`) và nộp bài làm quiz (`POST /v1/lessons/{id}/quiz`).<br>- Sử dụng tính năng dịch văn bản, dịch ảnh, dịch giọng nói (`POST /v1/translate*`).<br>- Tải gói dữ liệu offline (`GET /v1/sync/pull`). |
| **Thành viên (Member)** | `"member"` | `VERIFIED` | - Toàn bộ quyền của Khách.<br>- Quản lý phiên đăng nhập (`register`, `login`, `refresh`, `logout`, `me`).<br>- Gửi đóng góp câu song ngữ (`POST /v1/contributions`), đẩy đồng bộ đóng góp offline (`POST /v1/sync/push`).<br>- Xem danh sách đóng góp của chính mình (`GET /v1/contributions/mine`).<br>- Khi gọi API dịch có đính kèm Bearer token, lịch sử dịch (`translation_logs.user_id`) được gắn với tài khoản. |
| **Người kiểm duyệt (Reviewer)** | `"reviewer"` | `VERIFIED` | - Toàn bộ quyền của Thành viên.<br>- Xem danh sách hàng đợi đóng góp theo trạng thái (`GET /v1/contributions?status=...`).<br>- Duyệt hoặc từ chối câu đóng góp (`POST /v1/contributions/{id}/review`).<br>- Xuất dữ liệu câu song ngữ đã duyệt ra định dạng CSV (`GET /v1/training/pairs.csv`). |
| **Quản trị viên (Admin)** | `"admin"` | `PARTIAL` / `PROPOSED` | - Trong yêu cầu tổng thể có vai trò `admin` (quản lý hệ thống, danh mục, người dùng, kiểm duyệt và xuất dữ liệu).<br>- **Hiện trạng trong code**: Hàm `_reviewer(user)` tại `app/routers/community.py` đang kiểm tra cứng `if user.role != "reviewer": raise 403`. Nếu tài khoản có `role = "admin"` sẽ bị chặn. Cần cập nhật sang `user.role in ("reviewer", "admin")` và bổ sung phân quyền quản trị ở các phase tiếp theo. |

---

## 4. Các chức năng chính của hệ thống & Trạng thái hiện tại

Bảng tổng hợp đối chiếu giữa yêu cầu nghiệp vụ và hiện trạng trong source code Backend:

| STT | Phân hệ (Module) | Chức năng chi tiết | Trạng thái | Ghi chú kỹ thuật từ Source Code |
| :-: | :--- | :--- | :---: | :--- |
| 1 | **Health & Core** | Kiểm tra trạng thái dịch vụ (`GET /health`) | `PARTIAL` | Đã có tại `app/main.py`, trả về `{"status": "ok", "service": "api"}`, chưa kiểm tra kết nối DB thực tế. |
| 2 | **Foundation** | Quản lý Migration với Alembic & Global Error Handling | `MISSING` | Đã khai báo `alembic` trong `pyproject.toml` nhưng chưa khởi tạo thư mục migration; chưa có global exception handler thống nhất cho lỗi 422/500. |
| 3 | **Auth** | Đăng ký, Đăng nhập, Lấy thông tin `/me` | `VERIFIED` | Triển khai đầy đủ tại `app/routers/auth.py`, mật khẩu băm bằng Argon2 (`pwdlib[argon2]`). |
| 4 | **Auth** | Refresh Token Rotation & Logout | `VERIFIED` | Lưu SHA-256 hash của `jti` trong bảng `refresh_tokens`, xoay vòng 1 lần (`revoked_at`). |
| 5 | **Auth** | Đổi mật khẩu, Quên/Đặt lại mật khẩu | `MISSING` | Chưa có endpoint đổi mật khẩu hoặc reset mật khẩu trong `app/routers/auth.py`. |
| 6 | **Catalog** | Tra cứu Ngôn ngữ, Dân tộc, Di sản văn hóa | `PARTIAL` | Đã có `GET /v1/languages`, `GET /v1/peoples`, `GET /v1/peoples/{slug}`. Chưa có API chi tiết từng ngôn ngữ (`GET /v1/languages/{code}`), tìm kiếm/lọc/phân trang danh mục. |
| 7 | **AI Translation** | Dịch văn bản (`POST /v1/translate`) | `VERIFIED` | Gọi `MlClient.translate`, kiểm tra mã ngôn ngữ hợp lệ, lưu `translation_logs`. |
| 8 | **AI Translation** | Dịch hình ảnh OCR (`POST /v1/translate/image`) | `PARTIAL` | Gọi `MlClient.ocr` -> dịch văn bản nhận diện được. Đã giới hạn kích thước 8 MB, nhưng chưa kiểm tra chặt MIME type/magic bytes của file ảnh. |
| 9 | **AI Translation** | Dịch giọng nói ASR (`POST /v1/translate/speech`) | `PARTIAL` | Gọi `MlClient.asr` -> dịch văn bản nhận diện được (xử lý cả trường hợp model ASR trả về `spoken_language` khác `language`). Giới hạn 20 MB, chưa kiểm tra chặt định dạng file âm thanh. |
| 10 | **AI Translation** | Xem lịch sử dịch thuật của người dùng | `MISSING` | Backend đã ghi bảng `translation_logs` nhưng chưa có API `GET /v1/translate/history` để người dùng tra cứu lại. |
| 11 | **Learning & Quiz** | Danh sách bài học, Chi tiết bài học, Chấm điểm Quiz | `VERIFIED` | Đã có `GET /v1/lessons`, `GET /v1/lessons/{id}`, `POST /v1/lessons/{id}/quiz`. Ẩn hoàn toàn trường `is_correct` khi trả câu hỏi. |
| 12 | **Learning & Quiz** | Lưu kết quả làm bài & Theo dõi tiến độ học tập | `MISSING` | Hiện tại `POST /v1/lessons/{id}/quiz` chỉ chấm điểm tức thời (stateless) và trả kết quả, chưa lưu lịch sử/tiến độ học tập vào Database. |
| 13 | **Community** | Gửi câu đóng góp, Xem đóng góp cá nhân, Duyệt câu | `PARTIAL` | Đã có `POST /v1/contributions`, `GET /v1/contributions/mine`, `GET /v1/contributions`, `POST /v1/contributions/{id}/review`. Tuy nhiên chưa chặn trường hợp reviewer tự duyệt câu của chính mình và chưa hỗ trợ đính kèm file âm thanh. |
| 14 | **Offline Sync** | Đồng bộ đóng góp (`push`) & tải gói dữ liệu (`pull`) | `PARTIAL` | Đã có `POST /v1/sync/push` (idempotent theo `client_id`) và `GET /v1/sync/pull`. Chưa hỗ trợ lọc `pull` theo mốc thời gian (`since` / `updated_after`) để giảm băng thông. |
| 15 | **Training Export** | Xuất dữ liệu huấn luyện đã duyệt (`GET /v1/training/pairs.csv`) | `PARTIAL` | Đã xuất CSV các bản ghi `status = 'approved'`, chưa hỗ trợ bộ lọc theo ngôn ngữ (`language_code`), khoảng thời gian và chưa cho phép role `admin`. |

---

## 5. Phạm vi hiện tại và Định hướng mở rộng

### 5.1. Phạm vi hiện tại (Bảo toàn 100% tương thích)
- Giữ nguyên toàn bộ đường dẫn URL, cấu trúc JSON trả về và hành vi của các endpoint `/health` và `/v1/*` đang hoạt động để không làm gãy ứng dụng di động Flutter (`vietlangai-mob`) cũng như bộ kiểm thử hiện có (`tests/test_api.py`, `tests/test_scoring.py`).
- Giữ nguyên bộ dữ liệu chuẩn trong `shared/languages.json` (5 dân tộc Tày, Ê Đê, Chăm, H'Mông, Jrai và 7 ngôn ngữ).

### 5.2. Định hướng hoàn thiện và mở rộng theo lộ trình
1. **Chuẩn hóa kiến trúc & Database (Phase 1 - 2)**:
   - Thiết lập Alembic quản lý schema migrations.
   - Bổ sung bảng/cột phục vụ theo dõi tiến độ học tập (`learning_progress` / `quiz_attempts`) và lịch sử duyệt đóng góp nếu cần, đảm bảo không phá vỡ các bảng hiện có.
   - Chuyển đổi cấu hình kết nối linh hoạt cho **AWS RDS PostgreSQL** (bên cạnh Supabase/SQLite).
2. **Hoàn thiện tính năng cốt lõi & Bảo mật (Phase 3 - 6)**:
   - Bổ sung phân quyền cho `admin` kế thừa quyền `reviewer`, chặn tự duyệt đóng góp của chính mình.
   - Bổ sung API đổi mật khẩu, xem lịch sử dịch thuật, lưu tiến độ học tập, lọc dữ liệu khi export CSV và đồng bộ incremental (`since`).
   - Kiểm tra chặt định dạng tệp tải lên (Image/Audio), bổ sung Rate Limiting, Logging thời gian xử lý ML Service và bộ kiểm thử toàn diện.
3. **Sẵn sàng triển khai AWS EC2 + RDS (Phase 7)**:
   - Hoàn thiện Dockerfile, cấu hình Nginx, systemd/docker-compose, biến môi trường `.env.example` và tài liệu hướng dẫn triển khai lên AWS EC2 kết nối AWS RDS PostgreSQL trong private subnet.


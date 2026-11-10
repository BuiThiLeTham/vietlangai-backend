# 11. FINAL BACKEND QUALITY & READINESS AUDIT REPORT

> **Dự án:** Ngôn Sắc Việt (VietLangAI Backend)  
> **Ngày thực hiện Audit:** 2026-11-10  
> **Phạm vi:** Kiểm định độc lập toàn bộ mã nguồn, cơ sở dữ liệu, миграции Alembic, bảo mật, tích hợp AI, bộ kiểm thử Pytest và cấu hình triển khai AWS EC2 + RDS PostgreSQL.  
> **Chế độ thực hiện:** **AUDIT ONLY** (Không chỉnh sửa mã nguồn, không thay đổi cơ sở dữ liệu, không tạo migration mới).

---

## 1. Tổng quan Chất lượng Backend (Executive Summary)

Sau khi hoàn thành các giai đoạn từ Phase 0 đến Phase 7, hệ thống Backend `vietlangai-backend` đã đạt được bộ khung chức năng hoàn chỉnh cho toàn bộ các phân hệ nghiệp vụ cốt lõi:
- **Xác thực & Phân quyền**: Đăng ký, đăng nhập, cấp JWT Access Token, xoay vòng Refresh Token (lưu mã băm SHA-256 của `jti`), đăng xuất, đổi mật khẩu và phân quyền theo vai trò (`member`, `reviewer`, `admin`).
- **Danh mục & Di sản văn hóa**: Quản lý 7 ngôn ngữ, 5 dân tộc thiểu số (Tày, Ê Đê, Chăm, H'Mông, Jrai) và tư liệu di sản văn hóa kèm bộ lọc, tìm kiếm, phân trang.
- **Học tập & Trắc nghiệm**: Quản lý bài học, câu giao tiếp mẫu đã xác minh (`verified = true`), ẩn đáp án trắc nghiệm (`is_correct`), chấm điểm bài làm và lưu lịch sử/tiến độ học tập (`quiz_attempts`).
- **Tích hợp AI/ML**: Điều phối dịch văn bản, nhận diện chữ từ ảnh (OCR), nhận diện giọng nói (ASR), bảo toàn văn bản nhận diện khi mô hình dịch chưa sẵn sàng, và lưu vết lịch sử dịch thuật (`translation_logs`).
- **Cộng đồng & Đồng bộ ngoại tuyến**: Gửi câu đóng góp, chống trùng lặp idempotent theo `client_id`, hàng đợi kiểm duyệt, đồng bộ `push`/`pull` và xuất dữ liệu huấn luyện ra CSV.

Tuy nhiên, qua rà soát kỹ thuật chuyên sâu ở cấp độ **Production Readiness**, hệ thống hiện đang tồn tại **2 vấn đề mức HIGH**, **7 vấn đề mức MEDIUM** và **4 vấn đề mức LOW** liên quan đến xung đột giữa `create_all` và Alembic, độ dài khóa bí mật JWT mặc định, logic kiểm tra MIME type khi upload tệp, cách lấy IP trong Rate Limiter sau Reverse Proxy, và việc chưa kiểm chứng trực tiếp định dạng lỗi `422` mới với mã nguồn Flutter.

---

## 2. Danh mục các Hạng mục Đã Kiểm tra (Audit Checklist)

| STT | Hạng mục Kiểm tra | Các File / Thành phần Đối chiếu | Trạng thái |
| :-: | :--- | :--- | :---: |
| 1 | **API Compatibility Audit** | `app/main.py`, `app/core/exceptions.py`, `app/routers/*.py`, `tests/test_api.py` | Đã kiểm tra |
| 2 | **Database & Migration Audit** | `app/core/db.py`, `app/models.py`, `alembic/env.py`, `alembic/versions/0001_initial_schema.py`, `supabase/migrations/0001_init.sql` | Đã kiểm tra |
| 3 | **Security Audit** | `app/core/security.py`, `app/core/deps.py`, `app/core/config.py`, `app/core/rate_limit.py`, `app/seed.py` | Đã kiểm tra |
| 4 | **AI Integration Audit** | `app/integrations/ml_client.py`, `app/routers/translate.py`, `shared/languages.json` | Đã kiểm tra |
| 5 | **AWS Deployment Audit** | `Dockerfile`, `.env.example`, `docs/10_AWS_DEPLOYMENT_GUIDE.md`, `app/core/db.py` | Đã kiểm tra |
| 6 | **Testing & Coverage Audit** | `tests/conftest.py`, `tests/test_api.py`, `tests/test_scoring.py`, `tests/test_comprehensive.py` | Đã kiểm tra |

---

## 3. Bảng Tổng hợp các Lỗi và Vấn đề Phát hiện (Findings & Severity Matrix)

> **Phân loại mức độ nghiêm trọng:**
> - **CRITICAL**: Gây mất dữ liệu, lộ dữ liệu nhạy cảm ngay lập tức hoặc làm sập hoàn toàn hệ thống. *(0 phát hiện)*
> - **HIGH**: Gây lỗi khi chạy migration nâng cấp trên Production hoặc tiềm ẩn lỗ hổng bảo mật lớn nếu cấu hình thiếu sót. *(2 phát hiện)*
> - **MEDIUM**: Có nguy cơ gây lỗi tương thích biên, giảm hiệu năng khi tải cao hoặc làm yếu lớp phòng vệ bảo mật. *(7 phát hiện)*
> - **LOW**: Các điểm chưa tối ưu về vận hành, cảnh báo thư viện hoặc chuẩn hóa mã nguồn. *(4 phát hiện)*

| Mã Vấn đề | Mức độ | Phân hệ | Vị trí trong Source Code | Mô tả Bằng chứng Kỹ thuật |
| :--- | :---: | :--- | :--- | :--- |
| **AUD-DB-01** | **HIGH** | Database & Migration | `app/core/db.py:65-66`<br>`app/main.py:17`<br>`alembic/versions/0001_initial_schema.py` | **Xung đột giữa `Base.metadata.create_all` và Alembic Migration**: Hàm `init_db()` vẫn gọi `Base.metadata.create_all` mỗi khi khởi động ứng dụng. Nếu ứng dụng khởi động trước khi chạy `alembic upgrade head`, toàn bộ 11 bảng được tạo nhưng bảng `alembic_version` không có bản ghi `0001_initial`, khiến lệnh `alembic upgrade head` sau đó bị lỗi `DuplicateTableError`. Ngược lại, trên database đã chạy `0001_init.sql` (10 bảng cũ), migration `0001_initial` cũng sẽ lỗi vì cố tạo lại 10 bảng đã tồn tại thay vì chỉ tạo bảng mới `quiz_attempts`. |
| **AUD-SEC-01** | **HIGH** | Security / Auth | `app/core/config.py:17`<br>`app/core/security.py:22,33,41`<br>`tests/conftest.py:4` | **Khóa `JWT_SECRET` mặc định yếu và thiếu kiểm tra bắt buộc khi chạy Production**: Giá trị mặc định `jwt_secret = "dev-only-change-me"` (18 bytes) và trong test là `"test-secret"` (11 bytes), ngắn hơn mức tối thiểu 32 bytes (256 bits) cho thuật toán `HS256` theo chuẩn RFC 7518 Section 3.2 (PyJWT phát cảnh báo `InsecureKeyLengthWarning`). Quan trọng hơn, hệ thống chưa chặn khởi động khi `app_env == "production"` mà `jwt_secret` vẫn giữ giá trị mặc định. |
| **AUD-API-01** | **MEDIUM** | API / Exception Handler | `app/core/exceptions.py:30-49` | **Thay đổi cấu trúc JSON của lỗi `422 RequestValidationError`**: Mặc định FastAPI trả về `{"detail": [{"loc": ..., "msg": ..., "type": ...}]}` (kiểu `List`). Handler mới bọc lại thành `{"detail": {"code": "validation_error", "message": "...", "errors": [...]}}` (kiểu `Map/Object`). Nếu ứng dụng Flutter (`vietlangai-mob`) đang ép kiểu `response.data['detail'] as List` khi bắt lỗi 422, ứng dụng di động có thể gặp lỗi ép kiểu (`TypeError`). |
| **AUD-SEC-04** | **MEDIUM** | Security / File Upload | `app/routers/translate.py:16-50` | **Lỗ hổng logic kiểm tra định dạng tệp tải lên (`_validate_upload`)**: Tập `ALLOWED_IMAGE_TYPES` (dòng 16) và `ALLOWED_AUDIO_TYPES` (dòng 31) đều chứa `"application/octet-stream"`. Ở dòng 45–46, điều kiện `type_ok = not ctype or ctype in allowed_types` và `if not type_ok and not ext_ok:` dẫn đến việc: nếu kẻ tấn công gửi file thực thi `malware.exe` nhưng đặt header `Content-Type: application/octet-stream` (hoặc bỏ trống `Content-Type`), `type_ok` sẽ bằng `True` và tệp độc hại sẽ **vượt qua** bước kiểm tra dù đuôi `.exe` không hợp lệ. Ngoài ra chưa kiểm tra magic bytes (header nhị phân của ảnh/audio). |
| **AUD-SEC-03** | **MEDIUM** | Security / Rate Limit | `app/core/rate_limit.py:16,30-31` | **Rate Limiter dùng IP trực tiếp và không giới hạn bộ nhớ**: `request.client.host` (dòng 30) khi chạy sau Nginx Reverse Proxy hoặc AWS ALB sẽ luôn nhận IP của proxy (`127.0.0.1`), khiến mọi người dùng bị tính chung vào một giỏ giới hạn duy nhất. Đồng thời `self._buckets = defaultdict(deque)` lưu trong RAM của từng worker và không xóa các key cũ sau khi hết hạn, có nguy cơ rò rỉ bộ nhớ (memory leak) nếu bị tấn công từ nhiều IP. |
| **AUD-SEC-02** | **MEDIUM** | Security / Config | `app/core/config.py:31-32,37` | **Giá trị mặc định trong code của các cờ bảo mật đang mở**: Trong `Settings`, mặc định `seed_demo_user = True`, `allow_self_review = True`, `rate_limit_enabled = False`. Nếu triển khai lên server mà quên cấu hình `APP_ENV=production` hoặc thiếu các biến này trong `.env`, hệ thống sẽ tự tạo tài khoản reviewer mặc định (`Demo1234`), cho phép reviewer tự duyệt bài của mình và tắt Rate Limiting. |
| **AUD-DB-02** | **MEDIUM** | Database Schema | `supabase/migrations/0001_init.sql:127-150`<br>`alembic/versions/0001_initial_schema.py` | **Chưa đồng nhất nguồn Migration giữa SQL và Alembic**: File `supabase/migrations/0001_init.sql` chứa các câu lệnh bật Row-Level Security (`ENABLE ROW LEVEL SECURITY`), tạo Policy và tạo View `quiz_choices_public`, nhưng bản migration Alembic `0001_initial_schema.py` chưa bao gồm các đối tượng này. |
| **AUD-AI-01** | **MEDIUM** | AI Integration / Performance | `app/integrations/ml_client.py:51` | **Khởi tạo mới `httpx.AsyncClient` trên mỗi request**: Hàm `MlClient._post` mở và đóng một `httpx.AsyncClient` mới cho từng lần gọi `/v1/translate`, `/v1/ocr`, `/v1/asr` thay vì tái sử dụng Connection Pool chung trong vòng đời ứng dụng (`lifespan`), gây tốn chi phí bắt tay TCP/TLS khi tải đồng thời cao. |
| **AUD-AWS-01** | **MEDIUM** | AWS RDS / Database | `app/core/db.py:39-43` | **Cắt bỏ tham số Query String của `DATABASE_URL` và cấu hình SSL**: Dòng 39 `url = url.split("?", 1)[0]` xóa toàn bộ query string trên chuỗi kết nối PostgreSQL. Đồng thời `connect_args["ssl"] = "require"` chỉ mã hóa đường truyền mà chưa hỗ trợ cấu hình `ssl.SSLContext` để xác thực chứng chỉ gốc AWS RDS CA (`rds-ca-rsa2048-g1.pem`). |
| **AUD-TEST-01** | **MEDIUM** | Testing Coverage | `tests/` | **Một số nhánh logic mới chưa có bài test tự động**: Chưa có test kiểm tra thực tế `RateLimitMiddleware` trả mã `429`, chưa có test chặn tự duyệt (`403 self_review_forbidden`), chưa có test giả lập lỗi `httpx.TimeoutException` / `httpx.HTTPError` trong `MlClient`, và chưa có test chạy trực tiếp `alembic upgrade head`. |
| **AUD-API-02** | **LOW** | Health Check | `app/main.py:44-51` | **Endpoint `/health` luôn trả về HTTP `200 OK` kể cả khi mất kết nối DB**: Khi `check_db_health()` trả về `False`, body trả về `"status": "degraded"` nhưng HTTP status code vẫn là `200`, khiến AWS ALB / Docker Healthcheck có thể hiểu nhầm instance vẫn khỏe mạnh. |
| **AUD-AI-02** | **LOW** | Configuration | `app/routers/translate.py:13-14`<br>`app/core/config.py:26-27` | **Biến cấu hình `max_image_mb` và `max_audio_mb` chưa được nối vào Router**: `config.py` đã khai báo `max_image_mb` và `max_audio_mb` nhưng `translate.py` vẫn dùng hằng số cứng `MAX_BYTES = 8 * 1024 * 1024` và `MAX_AUDIO_BYTES = 20 * 1024 * 1024`. |
| **AUD-SEC-05** | **LOW** | Security / CSV Export | `app/routers/community.py:253-257` | **Nguy cơ CSV Formula Injection**: Khi xuất `/v1/training/pairs.csv`, nếu nội dung câu bắt đầu bằng các ký tự công thức (`=`, `+`, `-`, `@`), mở trực tiếp trên Microsoft Excel có thể kích hoạt thực thi công thức. |
| **AUD-AWS-02** | **LOW** | Docker / Deployment | `Dockerfile:1-9` | **Container chạy dưới quyền `root`**: `Dockerfile` chưa tạo user không có quyền root (`USER appuser`) và chưa khai báo chỉ thị `HEALTHCHECK`. |

---

## 4. Báo cáo Kiểm định Chi tiết theo Từng Phân hệ

### 4.1. API Compatibility Report (Đối chiếu với Flutter App)

1. **Tính tương thích của 22 Endpoint Gốc**:
   - Đã đối chiếu toàn bộ 22 endpoint ban đầu trong `app/routers/auth.py`, `catalog.py`, `learn.py`, `translate.py`, `community.py`: **100% đường dẫn URL, HTTP Method, Request Body và các trường trong Response JSON được giữ nguyên**.
   - Các tham số lọc/tìm kiếm mới (`role`, `q`, `limit`, `offset`, `language_code`, `family`, `level`, `updated_after`) đều là query parameters tùy chọn (`Optional`), khi không truyền sẽ trả về kết quả giống hệt phiên bản gốc.
   - Endpoint `GET /health` giữ nguyên `"status": "ok"` và `"service": "api"` (chỉ bổ sung thêm trường `"database": "ok"`).
2. **Tính tương thích của 5 Endpoint Mới**:
   - `POST /v1/auth/change-password`
   - `GET /v1/languages/{code}`
   - `GET /v1/heritage`
   - `GET /v1/lessons/progress/me` *(Đã đặt trước `/v1/lessons/{lesson_id}` tại `app/routers/learn.py:77` nên không bị xung đột route parameter)*.
   - `GET /v1/translate/history`
3. **Đánh giá Thay đổi Global Exception Handler (`app/core/exceptions.py`)**:
   - Với lỗi `HTTPException` (`400`, `401`, `403`, `404`, `409`, `413`, `503`): Giữ nguyên cấu trúc `{"detail": {"code": "...", "message": "..."}}` mà các router đã dùng từ đầu -> **An toàn 100% cho Flutter**.
   - Với lỗi `RequestValidationError` (`422`): Cấu trúc chuyển sang `{"detail": {"code": "validation_error", "message": "...", "errors": [...]}}` (`AUD-API-01`). Cần kiểm tra với đội Mobile trên môi trường Staging.

---

### 4.2. Database & Migration Report

1. **Models, Foreign Keys, Unique Constraints & Indexes (`app/models.py`)**:
   - Đầy đủ 11 bảng với khóa chính UUID/Code, khóa ngoại rõ ràng và `ondelete="CASCADE"` trên `refresh_tokens.user_id`, `heritage_items.group_id`, `phrases.lesson_id`, `quiz_questions.lesson_id`, `quiz_choices.question_id`, `quiz_attempts.user_id`, `quiz_attempts.lesson_id`.
   - Đã có Unique Constraints trên `users.email`, `refresh_tokens.token_hash`, `ethnic_groups.slug`, `heritage_items(group_id, title_vi)`, `contributions.client_id`.
2. **Đánh giá Nguồn Migration Chính thức**:
   - Hiện tại dự án đang có **3 cơ chế tạo bảng song song**:
     1. `Base.metadata.create_all` trong `app/core/db.py:66` (chạy tự động khi bật app).
     2. `alembic/versions/0001_initial_schema.py` (chạy qua CLI `alembic upgrade head`).
     3. `supabase/migrations/0001_init.sql` (chạy thủ công trên Supabase SQL Editor).
   - **Khuyến nghị kiến trúc bắt buộc trước khi lên Production**:
     - Chọn **Alembic** làm nguồn quản lý schema duy nhất cho AWS RDS PostgreSQL.
     - Trong `init_db()`, chỉ chạy `Base.metadata.create_all` khi dùng SQLite local/test (`if url.startswith("sqlite"):`), không tự gọi `create_all` trên PostgreSQL Production.
     - Nếu nâng cấp từ database đã có sẵn 10 bảng đầu tiên, cần tách bảng `quiz_attempts` và các index mới thành revision `0002_add_quiz_attempts.py` rồi `alembic stamp 0001_initial` trước khi `alembic upgrade head`.

---

### 4.3. Security Report

1. **Điểm mạnh đã được xác minh**:
   - Mật khẩu băm bằng **Argon2id** (`pwdlib[argon2]`).
   - JWT tách biệt rõ `"typ": "access"` và `"typ": "refresh"`.
   - Refresh token lưu dưới dạng băm SHA-256 (`token_hash`), xoay vòng 1 lần (`revoked_at`) và tự động thu hồi toàn bộ khi đổi mật khẩu (`app/routers/auth.py:168-177`).
   - Toàn bộ truy vấn ORM tham số hóa, chống SQL Injection; ẩn hoàn toàn đáp án `is_correct` khi lấy bài học; ẩn thông tin cá nhân khi xuất `/v1/training/pairs.csv`.
   - Không có dòng lệnh `logger` nào ghi mật khẩu, JWT token hoặc chuỗi kết nối DB chứa password ra log.
2. **Các điểm yếu cần khắc phục trước khi lên Production**:
   - Bắt buộc kiểm tra độ dài `JWT_SECRET >= 32` ký tự và cấm dùng giá trị mặc định khi `APP_ENV=production` (`AUD-SEC-01`).
   - Sửa điều kiện logic trong `_validate_upload` (`app/routers/translate.py:45-46`) từ `and` sang kiểm tra chặt cả phần mở rộng và magic bytes, không cho phép `application/octet-stream` bỏ qua kiểm tra đuôi file (`AUD-SEC-04`).
   - Hỗ trợ đọc IP thực từ header `X-Forwarded-For` (khi cấu hình trusted proxy) và giới hạn kích thước bộ nhớ trong `RateLimitMiddleware` (`AUD-SEC-03`).

---

### 4.4. AI Integration Report

- **Cơ chế Timeout & Chịu lỗi**: `MlClient` đã xử lý đầy đủ `httpx.TimeoutException` -> `503 ml_timeout`, `httpx.HTTPError` -> `503 ml_unavailable`, và JSON không hợp lệ -> `503 ml_error`.
- **Xử lý OCR & ASR**: Giữ nguyên văn bản nhận diện (`recognized_text`) kèm cảnh báo (`warnings`) khi mô hình dịch trả về `422`, và xử lý chính xác trường hợp mô hình ASR nghe tiếng dân tộc (`spoken_language="hmn"`) nhưng xuất văn bản tiếng Việt (`language="vi"`).
- **Lịch sử dịch thuật**: Lưu đầy đủ vào `translation_logs` (cắt an toàn ở 4000 ký tự) và cung cấp API `GET /v1/translate/history` có phân trang theo người dùng hiện tại.
- **Điểm cần tối ưu**: Chuyển `httpx.AsyncClient` sang khởi tạo một lần trong `lifespan` để tái sử dụng kết nối TCP/TLS (`AUD-AI-01`).

---

### 4.5. AWS Deployment Readiness Report

- **Hạ tầng mạng & RDS**: Tài liệu `docs/10_AWS_DEPLOYMENT_GUIDE.md` và `.env.example` đã thiết kế chuẩn mô hình EC2 ở Public Subnet (sau Nginx HTTPS) và RDS PostgreSQL ở Private Subnet (chỉ mở cổng `5432` cho Security Group của EC2).
- **Cần hoàn thiện trước khi Cutover Production**:
  1. Giữ lại các tham số query hợp lệ hoặc cấu hình `SSLContext` xác thực chứng chỉ RDS CA trong `app/core/db.py` (`AUD-AWS-01`).
  2. Trả mã HTTP `503` tại `/health` khi kết nối DB thất bại để AWS ALB / Nginx phát hiện sự cố chính xác (`AUD-API-02`).
  3. Bổ sung non-root user vào `Dockerfile` (`AUD-AWS-02`).

---

## 5. Kết quả Kiểm thử Thực tế (Testing Audit Results)

Lệnh thực thi kiểm thử thực tế:
```powershell
.venv\Scripts\python.exe -m pytest -v
```

- **Tổng số test cases**: **17**
  - **Passed**: **17**
  - **Failed**: **0**
  - **Skipped**: **0**
  - **Warnings**: **17** (1 cảnh báo `StarletteDeprecationWarning` và 16 cảnh báo `InsecureKeyLengthWarning` do `JWT_SECRET="test-secret"` trong `tests/conftest.py` dài 11 bytes < 32 bytes).
- **Thời gian thực thi**: ~7.9 giây.
- **Công cụ đo Coverage**: Trong môi trường hiện tại chưa cài đặt `pytest-cov` nên chưa xuất báo cáo phần trăm dòng lệnh (line coverage %). Qua đối chiếu trực tiếp mã nguồn, các nhánh chưa được test tự động gọi tới đã được liệt kê cụ thể tại mục **`AUD-TEST-01`**.

---

## 6. Kết luận Cuối cùng (Final Verdict)

Dựa trên toàn bộ bằng chứng từ mã nguồn, cơ sở dữ liệu, cấu hình bảo mật và kết quả kiểm thử thực tế:

> ### **KẾT LUẬN: `READY FOR STAGING, NOT PRODUCTION`**

### Lý do đưa ra kết luận:
1. **Đủ điều kiện triển khai lên môi trường STAGING (`READY FOR STAGING`)**:
   - Toàn bộ 27 API endpoints (22 endpoints gốc + 5 endpoints mở rộng) hoạt động ổn định, vượt qua 17/17 bài kiểm thử tích hợp và đơn vị, sẵn sàng để tích hợp kiểm thử (Integration UAT) cùng ứng dụng Flutter `vietlangai-mob` và ML Service.
2. **Chưa đủ điều kiện triển khai thẳng lên PRODUCTION (`NOT PRODUCTION`) cho đến khi xử lý 4 hạng mục bắt buộc sau**:
   1. **[`AUD-DB-01` - HIGH]**: Tách biệt `Base.metadata.create_all` (chỉ dùng cho SQLite test/dev) và Alembic migration trên PostgreSQL để tránh lỗi xung đột bảng khi nâng cấp schema trên AWS RDS.
   2. **[`AUD-SEC-01` & `AUD-SEC-02` - HIGH/MEDIUM]**: Bắt buộc kiểm tra `JWT_SECRET` tối thiểu 32 bytes và tắt mặc định `seed_demo_user` / `allow_self_review` khi chạy Production.
   3. **[`AUD-SEC-04` - MEDIUM]**: Khắc phục lỗ hổng logic `if not type_ok and not ext_ok` với `application/octet-stream` trong `_validate_upload` tại `app/routers/translate.py`.
   4. **[`AUD-API-01` - MEDIUM]**: Xác nhận trên môi trường Staging rằng ứng dụng Flutter không bị lỗi ép kiểu khi nhận cấu trúc JSON mới của lỗi `422 RequestValidationError`.


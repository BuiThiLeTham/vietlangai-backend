# 04. API REQUIREMENTS & CONTRACT SPECIFICATION

> **Tài liệu:** Đặc tả Chi tiết RESTful API, Schema Request/Response, Mã lỗi và Đối chiếu Mobile Contract  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)  
> **Đối chiếu:** `app/main.py`, `app/routers/*.py`, `tests/test_api.py`

---

## 1. Quy ước Chung của API

- **Base URL Prefix**:
  - Health Check: `/health`
  - Tất cả API nghiệp vụ: `/v1`
- **Định dạng dữ liệu**:
  - Request Body: `application/json` (trừ upload file OCR/ASR dùng `multipart/form-data`).
  - Response Body: `application/json` (trừ xuất dữ liệu huấn luyện `/v1/training/pairs.csv` trả về `text/plain` dạng CSV).
- **Cơ chế Xác thực (Authentication)**:
  - Header: `Authorization: Bearer <access_token>`
  - Thời hạn Access Token mặc định: `15 phút` (`900 giây`).
- **Cấu trúc Phản hồi Lỗi (Error Format)**:
  - Mọi lỗi nghiệp vụ được trả về qua HTTP status code tương ứng (`400`, `401`, `403`, `404`, `409`, `413`, `422`, `503`) với payload:
    ```json
    {
      "detail": {
        "code": "mã_lỗi_định_danh",
        "message": "Thông báo lỗi tiếng Việt rõ ràng cho người dùng"
      }
    }
    ```
- **Đối chiếu với Flutter App (`vietlangai-mob`)**:
  - Repository `https://github.com/minhduy6868/vietlangai-mob` hiện ở chế độ riêng tư/ngoài workspace (`UNKNOWN` mã nguồn trực tiếp phía client).
  - Tuy nhiên, toàn bộ contract giữa Flutter App và Backend đã được ghi nhận rõ trong `README.md`, `.env.example`, các router trong `app/routers/*` và bộ kiểm thử tích hợp `tests/test_api.py` (bao gồm cả luồng đồng bộ offline `/v1/sync/push` và `/v1/sync/pull`).
  - **Nguyên tắc bất khả xâm phạm**: Giữ nguyên 100% URL, HTTP Method, tên trường Request/Response của toàn bộ **22 endpoint hiện có**. Các tham số lọc/phân trang mới phải là `Optional` (query parameters có giá trị mặc định) để không phá vỡ ứng dụng di động.

---

## 2. Tổng hợp Danh sách API theo Module

### 2.1. Module Health & System

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 1 | `GET` | `/health` | Public | `PARTIAL` | Kiểm tra trạng thái hoạt động của API và kết nối Database. |

#### Chi tiết `GET /health`
- **Response `200 OK`**:
  ```json
  {
    "status": "ok",
    "service": "api"
  }
  ```
  *(Đề xuất mở rộng tương thích ngược: giữ nguyên `"status": "ok", "service": "api"` và có thể bổ sung `"database": "ok"`).*

---

### 2.2. Module Authentication (`/v1/auth`)

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 2 | `POST` | `/v1/auth/register` | Public | `VERIFIED` | Đăng ký tài khoản thành viên mới và nhận cặp JWT token. |
| 3 | `POST` | `/v1/auth/login` | Public | `VERIFIED` | Đăng nhập bằng email & mật khẩu. |
| 4 | `POST` | `/v1/auth/refresh` | Public (Refresh Token) | `VERIFIED` | Xoay vòng Refresh Token, thu hồi token cũ và cấp cặp token mới. |
| 5 | `POST` | `/v1/auth/logout` | Public (Refresh Token) | `VERIFIED` | Thu hồi Refresh Token hiện tại (`204 No Content`). |
| 6 | `GET` | `/v1/auth/me` | Bearer (`member`+) | `VERIFIED` | Lấy thông tin người dùng đang đăng nhập. |
| 7 | `POST` | `/v1/auth/change-password` | Bearer (`member`+) | `MISSING` | Đổi mật khẩu tài khoản hiện tại và thu hồi các refresh token cũ. |

#### Chi tiết Request / Response – Module Auth

1. **`POST /v1/auth/register`** (`Status: 201 Created`)
   - **Request Body (`RegisterIn`)**:
     ```json
     {
       "email": "member@ngonsacviet.example.com",
       "password": "password123",
       "display_name": "Nguyễn Văn A"
     }
     ```
     - Validation: `email` đúng chuẩn `EmailStr`; `password` từ `8..128` ký tự; `display_name` từ `1..120` ký tự (tự động `.strip()`).
   - **Response Body (`TokenOut`)**:
     ```json
     {
       "access_token": "eyJhbGciOiJIUzI1NiIs...",
       "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
       "token_type": "bearer",
       "expires_in": 900
     }
     ```
   - **Errors**: `409 Conflict` (`{"code": "email_taken", "message": "Email đã được đăng ký."}`).

2. **`POST /v1/auth/login`** (`Status: 200 OK`)
   - **Request Body (`LoginIn`)**:
     ```json
     {
       "email": "member@ngonsacviet.example.com",
       "password": "password123"
     }
     ```
   - **Response Body**: `TokenOut`.
   - **Errors**: `401 Unauthorized` (`{"code": "invalid_login", "message": "Email hoặc mật khẩu không đúng."}`).

3. **`POST /v1/auth/refresh`** (`Status: 200 OK`) & **`POST /v1/auth/logout`** (`Status: 204 No Content`)
   - **Request Body (`RefreshIn`)**:
     ```json
     {
       "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
     }
     ```
   - **Errors (`/refresh`)**: `401 Unauthorized` (`{"code": "unauthorized", "message": "Phiên đăng nhập không hợp lệ."}`).

4. **`GET /v1/auth/me`** (`Status: 200 OK`)
   - **Response Body (`UserOut`)**:
     ```json
     {
       "id": "550e8400-e29b-41d4-a716-446655440000",
       "email": "member@ngonsacviet.example.com",
       "display_name": "Nguyễn Văn A",
       "role": "member"
     }
     ```

5. **`POST /v1/auth/change-password`** (`MISSING` -> Cần bổ sung ở Phase 3)
   - **Request Body (`ChangePasswordIn`)**:
     ```json
     {
       "current_password": "password123",
       "new_password": "newPassword456"
     }
     ```
   - **Response**: `204 No Content` (hoặc `200 OK`).
   - **Errors**: `400 Bad Request` / `401 Unauthorized` nếu `current_password` sai.

---

### 2.3. Module Catalog: Ngôn ngữ, Dân tộc & Di sản (`/v1`)

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 8 | `GET` | `/v1/languages` | Public | `VERIFIED` | Danh sách ngôn ngữ (hỗ trợ lọc `role`, tìm kiếm `q`). |
| 9 | `GET` | `/v1/languages/{code}` | Public | `MISSING` | Chi tiết một ngôn ngữ theo mã `code`. |
| 10 | `GET` | `/v1/peoples` | Public | `VERIFIED` | Danh sách dân tộc (hỗ trợ lọc `language_code`, `family`, tìm kiếm `q`). |
| 11 | `GET` | `/v1/peoples/{slug}` | Public | `VERIFIED` | Chi tiết dân tộc kèm thông tin ngôn ngữ và danh sách di sản văn hóa (`heritage`). |
| 12 | `GET` | `/v1/heritage` | Public | `PROPOSED` | Danh sách các mục di sản văn hóa (lọc theo `group_slug`, `kind`, tìm kiếm `q`). |

#### Chi tiết Request / Response – Module Catalog

1. **`GET /v1/languages`** (`Status: 200 OK`)
   - **Query Params (Optional - Proposed)**: `role` (`ethnic` | `pivot`), `q` (từ khóa tìm kiếm).
   - **Response Body**:
     ```json
     [
       {
         "code": "tyz",
         "iso639_3": "tyz",
         "name_vi": "Tiếng Tày",
         "name_en": "Tay",
         "script": "Latn",
         "family": "Tai-Kadai",
         "role": "ethnic",
         "evaluation_tier": 1,
         "orthography": "Latin theo chữ Quốc ngữ"
       }
     ]
     ```

2. **`GET /v1/peoples`** (`Status: 200 OK`)
   - **Query Params (Optional - Proposed)**: `language_code`, `family`, `q`.
   - **Response Body**:
     ```json
     [
       {
         "slug": "tay",
         "name_vi": "Người Tày",
         "name_en": "Tay people",
         "family": "Tai-Kadai",
         "region_vi": "Cao Bằng, Lạng Sơn, Bắc Kạn, Tuyên Quang, Thái Nguyên và các tỉnh phía Bắc",
         "region_en": "Cao Bang, Lang Son, Bac Kan, Tuyen Quang, Thai Nguyen and other northern provinces",
         "language_code": "tyz"
       }
     ]
     ```

3. **`GET /v1/peoples/{slug}`** (`Status: 200 OK`)
   - **Response Body**: Bao gồm đầy đủ các trường của `/v1/peoples` cộng thêm `origin_vi`, `origin_en`, object `language` và mảng `heritage`:
     ```json
     {
       "slug": "tay",
       "name_vi": "Người Tày",
       "name_en": "Tay people",
       "family": "Tai-Kadai",
       "region_vi": "...",
       "region_en": "...",
       "origin_vi": "...",
       "origin_en": "...",
       "language_code": "tyz",
       "language": { "code": "tyz", "...": "..." },
       "heritage": [
         {
           "id": "uuid",
           "kind": "article",
           "title_vi": "Chữ và tiếng trong đời sống",
           "title_en": "Language in daily life",
           "body_vi": "...",
           "body_en": "...",
           "media_url": null
         }
       ]
     }
     ```
   - **Errors**: `404 Not Found` (`{"code": "not_found", "message": "Không thấy dân tộc."}`).

---

### 2.4. Module AI Translation (`/v1/translate`)

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 13 | `POST` | `/v1/translate` | Optional Bearer | `VERIFIED` | Dịch văn bản giữa các ngôn ngữ trong danh mục. |
| 14 | `POST` | `/v1/translate/image` | Optional Bearer | `PARTIAL` | Nhận diện chữ trong ảnh (OCR) và dịch sang ngôn ngữ đích. |
| 15 | `POST` | `/v1/translate/speech` | Optional Bearer | `PARTIAL` | Nhận diện giọng nói từ audio (ASR) và dịch sang ngôn ngữ đích. |
| 16 | `GET` | `/v1/translate/history` | Bearer (`member`+) | `MISSING` | Lấy lịch sử dịch thuật của người dùng đang đăng nhập. |

#### Chi tiết Request / Response – Module AI Translation

1. **`POST /v1/translate`** (`Status: 200 OK`)
   - **Request Body (`TranslateIn`)**:
     ```json
     {
       "text": "Xin chào",
       "source_lang": "vi",
       "target_lang": "tyz"
     }
     ```
     - Validation: `text` từ `1..2000` ký tự; `source_lang` (mặc định `"auto"`) và `target_lang` phải tồn tại trong bảng `languages`.
   - **Response Body**:
     ```json
     {
       "text": "Slương",
       "source_lang": "vi",
       "target_lang": "tyz",
       "detected_lang": null,
       "route": "direct",
       "engine": "nllb",
       "warnings": [],
       "steps": []
     }
     ```

2. **`POST /v1/translate/image`** & **`POST /v1/translate/speech`** (`Status: 200 OK`)
   - **Request (`multipart/form-data`)**:
     - `file`: Binary file (`<= 8 MB` cho ảnh, `<= 20 MB` cho audio).
     - `target_lang`: Mã ngôn ngữ đích (bắt buộc).
     - `source_lang`: Mã ngôn ngữ nguồn (mặc định `"auto"`).
   - **Response Body**:
     ```json
     {
       "text": "tôi về nhà",
       "recognized_text": "kuv mus tsev",
       "source_lang": "hmn",
       "target_lang": "vi",
       "detected_lang": "hmn",
       "route": "asr",
       "engine": "whisper",
       "warnings": [],
       "steps": []
     }
     ```
   - **Errors**:
     - `400 Bad Request` (`unknown_language`, `invalid_file_type`)
     - `413 Payload Too Large` (`file_too_large`)
     - `422 Unprocessable Entity` (lỗi từ ML khi dịch văn bản trực tiếp)
     - `503 Service Unavailable` (`ml_timeout`, `ml_unavailable`, `ml_error`)

---

### 2.5. Module Learning & Quiz (`/v1/lessons`)

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 17 | `GET` | `/v1/lessons` | Public | `VERIFIED` | Danh sách bài học (lọc theo `?language=<code>`), kèm các câu mẫu `phrases` đã kiểm chứng. |
| 18 | `GET` | `/v1/lessons/{lesson_id}` | Public | `VERIFIED` | Chi tiết bài học kèm danh sách câu hỏi và lựa chọn (ẩn `is_correct`). |
| 19 | `POST` | `/v1/lessons/{lesson_id}/quiz` | Optional Bearer | `PARTIAL` | Nộp đáp án bài trắc nghiệm, chấm điểm và lưu tiến độ nếu đã đăng nhập. |
| 20 | `GET` | `/v1/lessons/progress/me` | Bearer (`member`+) | `MISSING` | Xem lịch sử điểm số và tiến độ hoàn thành bài học của người dùng. |

#### Chi tiết Request / Response – Module Learning

1. **`POST /v1/lessons/{lesson_id}/quiz`** (`Status: 200 OK`)
   - **Request Body (`QuizIn`)**:
     ```json
     {
       "answers": [
         { "question_id": "uuid-q1", "choice_id": "uuid-c1" }
       ]
     }
     ```
   - **Response Body**:
     ```json
     {
       "score": 1,
       "total": 3,
       "results": [
         {
           "question_id": "uuid-q1",
           "correct": true,
           "explanation_vi": "Họ ngôn ngữ được ghi trong hồ sơ dân tộc.",
           "explanation_en": "The family is stored on the people profile."
         }
       ]
     }
     ```

---

### 2.6. Module Community, Offline Sync & Training Export (`/v1`)

| STT | Method | Endpoint | Auth | Trạng thái | Mô tả |
| :-: | :---: | :--- | :---: | :---: | :--- |
| 21 | `POST` | `/v1/contributions` | Bearer (`member`+) | `VERIFIED` | Gửi 1 cặp câu đóng góp mới (`status="pending"`). |
| 22 | `GET` | `/v1/contributions/mine` | Bearer (`member`+) | `VERIFIED` | Danh sách đóng góp của người dùng hiện tại. |
| 23 | `GET` | `/v1/contributions` | Bearer (`reviewer`, `admin`) | `PARTIAL` | Danh sách đóng góp theo trạng thái (`?status=pending`) để kiểm duyệt. |
| 24 | `POST` | `/v1/contributions/{contribution_id}/review` | Bearer (`reviewer`, `admin`) | `PARTIAL` | Duyệt (`approved`) hoặc từ chối (`rejected`) một câu đóng góp. |
| 25 | `POST` | `/v1/sync/push` | Bearer (`member`+) | `VERIFIED` | Đẩy hàng loạt tối đa 50 câu đóng góp từ thiết bị offline lên server. |
| 26 | `GET` | `/v1/sync/pull` | Public | `PARTIAL` | Tải gói dữ liệu offline (`languages`, `peoples`, `heritage`, `lessons`, `approved_contributions`). |
| 27 | `GET` | `/v1/training/pairs.csv` | Bearer (`reviewer`, `admin`) | `PARTIAL` | Xuất CSV các cặp câu đã duyệt phục vụ huấn luyện mô hình AI. |

---

## 3. Bảng Mã lỗi Chuẩn hóa (Standard Error Codes)

| Mã lỗi (`detail.code`) | HTTP Status | Ngữ cảnh phát sinh | Thông báo mặc định (`detail.message`) |
| :--- | :---: | :--- | :--- |
| `unauthorized` | `401` | Thiếu token, token hết hạn, sai chữ ký hoặc đã bị thu hồi | Phiên đăng nhập không hợp lệ. |
| `invalid_login` | `401` | Sai email hoặc mật khẩu khi đăng nhập | Email hoặc mật khẩu không đúng. |
| `forbidden` | `403` | Người dùng không có quyền `reviewer` / `admin` hoặc tự duyệt bài của mình | Chỉ người rà soát mới được duyệt câu. |
| `not_found` | `404` | Không tìm thấy dân tộc, ngôn ngữ, bài học hoặc đóng góp | Không thấy dân tộc. / Không thấy bài học. / Không thấy đóng góp. |
| `email_taken` | `409` | Đăng ký trùng địa chỉ email đã có trong hệ thống | Email đã được đăng ký. |
| `client_id_taken` | `409` | Gửi `client_id` trùng với đóng góp của một tài khoản khác | Mã đóng góp đã thuộc người khác. |
| `unknown_language` | `400` | Mã ngôn ngữ không nằm trong bảng `languages` | Không có mã ngôn ngữ `{code}`. |
| `same_language` | `400` | Câu nguồn và câu đích trong đóng góp có cùng mã ngôn ngữ | Câu nguồn và câu đích phải khác ngôn ngữ. |
| `invalid_file_type` | `400` | Tệp ảnh/audio tải lên rỗng hoặc sai định dạng cho phép | Định dạng tệp không được hỗ trợ. |
| `file_too_large` | `413` | Ảnh vượt quá 8 MB hoặc Audio vượt quá 20 MB | Ảnh vượt 8 MB. / Audio vượt 20 MB. |
| `validation_error` | `422` | Dữ liệu đầu vào không thỏa mãn ràng buộc Pydantic | Dữ liệu đầu vào không hợp lệ. |
| `ml_timeout` | `503` | ML Service không phản hồi trong thời gian `TEXT_TIMEOUT` / `FILE_TIMEOUT` | Bộ dịch phản hồi quá lâu, thử lại sau. |
| `ml_unavailable` | `503` | Không thể thiết lập kết nối HTTP tới ML Service | Bộ dịch chưa chạy. |
| `ml_error` | `503` | ML Service trả về phản hồi không phải JSON hợp lệ hoặc lỗi 5xx | Bộ dịch trả về dữ liệu không đọc được. |


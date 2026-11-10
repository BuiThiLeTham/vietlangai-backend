# 02. BACKEND REQUIREMENTS SPECIFICATION

> **Tài liệu:** Đặc tả Yêu cầu Chức năng (FR), Phi chức năng (NFR) và Quy tắc Nghiệp vụ (Business Rules)  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)

---

## 1. Quy ước Phân loại Trạng thái (Status Legend)

Mỗi yêu cầu trong tài liệu này được đánh giá trực tiếp dựa trên mã nguồn hiện tại của `vietlangai-backend`:
- **`VERIFIED`**: Đã có code triển khai đầy đủ và được kiểm chứng qua test hiện tại.
- **`PARTIAL`**: Đã có một phần trong code nhưng còn thiếu tính năng phụ, thiếu kiểm tra điều kiện biên hoặc cần mở rộng.
- **`MISSING`**: Có trong yêu cầu hệ thống nhưng chưa được triển khai trong code.
- **`BUG`**: Đã có code nhưng logic hiện tại gây lỗi hoặc sai lệch so với quy tắc nghiệp vụ/bảo mật.
- **`PROPOSED`**: Đề xuất cải tiến kỹ thuật để đảm bảo kiến trúc, bảo mật và vận hành trên AWS.
- **`UNKNOWN`**: Phụ thuộc vào thông tin bên ngoài chưa truy cập được trực tiếp (ví dụ mã nguồn repo riêng tư `vietlangai-mob`).

---

## 2. Functional Requirements (FR)

### 2.1. Authentication & Authorization (`FR-AUTH`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-AUTH-001** | Đăng ký tài khoản | Người dùng đăng ký bằng `email`, `password` (8–128 ký tự), `display_name` (1–120 ký tự). Email tự động chuyển về chữ thường (`lower()`) và không được trùng lặp. | `VERIFIED` | - Trả về HTTP `201 Created` kèm `access_token`, `refresh_token`, `token_type="bearer"`, `expires_in`.<br>- Nếu email đã tồn tại, trả về HTTP `409 Conflict` với `code="email_taken"`. |
| **FR-AUTH-002** | Đăng nhập | Người dùng đăng nhập bằng `email` và `password`. Xác thực mật khẩu bằng Argon2 (`pwdlib`). | `VERIFIED` | - Trả về HTTP `200 OK` kèm cặp token mới.<br>- Sai email hoặc mật khẩu trả về HTTP `401 Unauthorized` với `code="invalid_login"`. |
| **FR-AUTH-003** | Làm mới phiên (Refresh Token Rotation) | Đổi `refresh_token` hợp lệ lấy cặp `access_token` và `refresh_token` mới; thu hồi ngay (`revoked_at = now`) refresh token vừa sử dụng. | `VERIFIED` | - Token hợp lệ & chưa thu hồi trả về `200 OK` với cặp token mới.<br>- Dùng lại refresh token cũ đã xoay vòng trả về `401 Unauthorized` (`code="unauthorized"`). |
| **FR-AUTH-004** | Đăng xuất | Thu hồi `refresh_token` hiện tại của người dùng bằng cách đánh dấu `revoked_at`. | `VERIFIED` | - Gọi `POST /v1/auth/logout` trả về `204 No Content`.<br>- Refresh token sau khi logout không thể dùng để gọi `/v1/auth/refresh`. |
| **FR-AUTH-005** | Lấy thông tin người dùng hiện tại | Trả về hồ sơ người dùng (`id`, `email`, `display_name`, `role`) từ JWT Access Token. | `VERIFIED` | - Gọi `GET /v1/auth/me` với Bearer token hợp lệ trả về `200 OK`.<br>- Không có token hoặc truyền refresh token thay vì access token trả về `401 Unauthorized`. |
| **FR-AUTH-006** | Đổi mật khẩu | Cho phép người dùng đã đăng nhập đổi mật khẩu khi cung cấp đúng `current_password` và `new_password` (tối thiểu 8 ký tự). | `MISSING` | - `POST /v1/auth/change-password` xác thực mật khẩu cũ, cập nhật `password_hash` mới và thu hồi các refresh token cũ của user. |
| **FR-AUTH-007** | Phân quyền theo vai trò (RBAC) | Hệ thống phân biệt rõ 3 vai trò: `member`, `reviewer`, `admin`. Các thao tác kiểm duyệt và xuất dữ liệu huấn luyện chỉ cho phép `reviewer` và `admin`. | `PARTIAL` / `BUG` | - Trong `app/routers/community.py`, hàm `_reviewer` hiện chỉ cho phép `user.role == "reviewer"` (chặn cả `admin`). Cần cho phép cả `reviewer` và `admin`. |

---

### 2.2. Catalog: Ngôn ngữ, Dân tộc & Di sản văn hóa (`FR-CAT`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-CAT-001** | Danh sách ngôn ngữ | Trả về danh sách các ngôn ngữ được hỗ trợ, sắp xếp theo `evaluation_tier` và `code`. | `VERIFIED` | - `GET /v1/languages` trả về đủ 7 ngôn ngữ chuẩn từ DB; hỗ trợ lọc/tìm kiếm tuỳ chọn (backward-compatible). |
| **FR-CAT-002** | Chi tiết ngôn ngữ | Lấy thông tin chi tiết một ngôn ngữ theo mã `code` kèm dân tộc và số lượng bài học liên quan. | `MISSING` | - `GET /v1/languages/{code}` trả về `200 OK` nếu tồn tại, hoặc `404 Not Found` (`code="not_found"`) nếu không có. |
| **FR-CAT-003** | Danh sách dân tộc | Trả về danh sách các dân tộc thiểu số trong hệ thống, sắp xếp theo `name_vi`. | `VERIFIED` | - `GET /v1/peoples` trả về danh sách 5 dân tộc (`tay`, `ede`, `cham`, `hmong`, `jrai`). Hỗ trợ thêm query tìm kiếm `q`, lọc `language_code` hoặc `family` mà không phá vỡ mặc định. |
| **FR-CAT-004** | Chi tiết dân tộc & Di sản văn hóa | Trả về thông tin chi tiết dân tộc theo `slug`, kèm thông tin ngôn ngữ (`language`) và danh sách mục di sản văn hóa (`heritage`). | `VERIFIED` | - `GET /v1/peoples/{slug}` trả về `200 OK` với đầy đủ `origin_vi`, `origin_en`, `language`, `heritage`.<br>- Nếu `slug` không tồn tại, trả về `404 Not Found`. |
| **FR-CAT-005** | Tra cứu danh sách Di sản văn hóa | Cho phép lấy danh sách hoặc lọc riêng các mục di sản văn hóa (`heritage_items`) theo dân tộc (`group_slug`) hoặc loại hình (`kind`: `article`, `audio`, `video`, `image`). | `PARTIAL` | - Hiện tại di sản đã có trong `GET /v1/peoples/{slug}` và `GET /v1/sync/pull`. Có thể bổ sung `GET /v1/heritage` có lọc theo `group_slug` và `kind`. |

---

### 2.3. AI Translation: Văn bản, Hình ảnh (OCR), Giọng nói (ASR) (`FR-TRANS`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-TRANS-001** | Dịch văn bản (Text Translation) | Nhận văn bản (`1..2000` ký tự), `source_lang` (mặc định `"auto"`) và `target_lang`, kiểm tra ngôn ngữ hợp lệ trong bảng `languages`, chuyển tiếp tới ML Service (`/v1/translate`) và trả kết quả. | `VERIFIED` | - `POST /v1/translate` trả về `200 OK` với kết quả dịch.<br>- Ngôn ngữ không thuộc danh mục trả về `400 Bad Request` (`code="unknown_language"`). |
| **FR-TRANS-002** | Dịch văn bản từ hình ảnh (Image OCR + Translation) | Nhận file ảnh upload (`multipart/form-data`), giới hạn dung lượng $\le 8\text{ MB}$, gửi tới ML Service (`/v1/ocr`), sau đó dịch văn bản nhận diện được sang `target_lang`. | `PARTIAL` | - `POST /v1/translate/image` giữ lại `recognized_text` ngay cả khi chưa có mô hình dịch cho ngôn ngữ đó (khi ML trả 422).<br>- Ảnh $> 8\text{ MB}$ trả về `413 Payload Too Large` (`code="file_too_large"`).<br>- Cần bổ sung kiểm tra định dạng file ảnh hợp lệ (`image/jpeg`, `image/png`, `image/webp`). |
| **FR-TRANS-003** | Dịch giọng nói (Voice ASR + Translation) | Nhận file âm thanh upload (`multipart/form-data`), giới hạn dung lượng $\le 20\text{ MB}$, gửi tới ML Service (`/v1/asr`), xử lý ngôn ngữ nói (`spoken_language`) và ngôn ngữ chữ viết (`language`) trước khi dịch sang `target_lang`. | `PARTIAL` | - `POST /v1/translate/speech` trả về `recognized_text`, `text`, `detected_lang` và `warnings`.<br>- Nếu mô hình ASR nghe tiếng dân tộc (`spoken_language="hmn"`) và xuất ra chữ tiếng Việt (`language="vi"`), hệ thống không gọi dịch lại nếu `target_lang="vi"`, hoặc dịch từ `"vi"` sang `"en"` nếu `target_lang="en"`.<br>- Cần bổ sung kiểm tra định dạng file audio hợp lệ. |
| **FR-TRANS-004** | Lưu nhật ký dịch thuật (`TranslationLog`) | Mọi lần dịch thành công (`text`, `image`, `speech`) đều được ghi vào bảng `translation_logs` kèm `user_id` (nếu người dùng có gửi kèm Access Token). | `VERIFIED` | - Bản ghi `TranslationLog` được tạo trong DB với `mode`, `source_lang`, `target_lang`, `source_text` (cắt tối đa 4000 ký tự), `output_text`, `route`, `engine`, `created_at`. |
| **FR-TRANS-005** | Tra cứu lịch sử dịch thuật cá nhân | Người dùng đã đăng nhập có thể xem lại lịch sử các câu đã dịch của mình. | `MISSING` | - `GET /v1/translate/history` (yêu cầu đăng nhập) trả về danh sách lịch sử dịch thuật của `user.id` sắp xếp từ mới nhất, hỗ trợ phân trang/giới hạn (`limit`, `offset`). |

---

### 2.4. Learning & Quiz (`FR-LEARN`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-LEARN-001** | Danh sách bài học | Lấy danh sách bài học (`GET /v1/lessons`), hỗ trợ lọc theo mã ngôn ngữ (`?language=tyz`), kèm danh sách câu giao tiếp mẫu đã xác minh (`phrases` có `verified = true`). | `VERIFIED` | - Trả về danh sách bài học không kèm danh sách câu hỏi quiz (`with_questions=False`), chỉ trả về các `phrases` có `verified=True`. |
| **FR-LEARN-002** | Chi tiết bài học & Câu hỏi trắc nghiệm | Lấy chi tiết bài học (`GET /v1/lessons/{lesson_id}`) bao gồm cả các câu hỏi (`questions`) và lựa chọn (`choices`), nhưng **tuyệt đối ẩn trường `is_correct`** và lời giải thích trước khi nộp bài. | `VERIFIED` | - Trong JSON trả về của `GET /v1/lessons/{lesson_id}` không xuất hiện khóa `is_correct` hay `explanation_vi`/`explanation_en`.<br>- Nếu không tìm thấy bài học trả về `404 Not Found`. |
| **FR-LEARN-003** | Nộp bài và chấm điểm Quiz | Nhận danh sách câu trả lời (`answers: [{question_id, choice_id}]`) tại `POST /v1/lessons/{lesson_id}/quiz`, tính tổng điểm và trả kết quả từng câu kèm giải thích (`explanation_vi`, `explanation_en`). | `VERIFIED` | - Trả về `{"score": <số câu đúng>, "total": <tổng số câu của bài>, "results": [...]}`.<br>- Chấm đúng khi `choice_id` khớp với phương án có `is_correct = true`. |
| **FR-LEARN-004** | Lưu kết quả và theo dõi tiến độ học tập | Khi người dùng đã đăng nhập nộp bài quiz, hệ thống lưu lại kết quả làm bài (điểm số, tổng số câu, thời gian hoàn thành) và cung cấp API xem tiến độ học tập. | `MISSING` | - Khi gọi `POST /v1/lessons/{lesson_id}/quiz` có kèm Bearer token, lưu bản ghi kết quả học tập vào DB.<br>- Cung cấp `GET /v1/lessons/progress/me` (hoặc `/v1/learn/progress`) trả về tiến độ các bài đã học của người dùng. |

---

### 2.5. Community Contribution & Moderation (`FR-COMM`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-COMM-001** | Gửi câu đóng góp mới | Thành viên đã đăng nhập gửi cặp câu song ngữ (`client_id`, `language_code`, `source_lang`, `target_lang`, `source_text`, `target_text`, `note`) qua `POST /v1/contributions`. | `VERIFIED` | - Chuẩn hóa khoảng trắng (`" ".join(text.split())`), khởi tạo `status = "pending"`.<br>- Chặn `source_lang == target_lang` (`400 same_language`) và mã ngôn ngữ không tồn tại (`400 unknown_language`). |
| **FR-COMM-002** | Chống trùng lặp theo `client_id` | Nếu thiết bị gửi lại một `client_id` đã tồn tại của chính người dùng đó, trả về bản ghi hiện có thay vì tạo bản ghi trùng. Nếu `client_id` thuộc về người dùng khác, báo lỗi `409 Conflict`. | `VERIFIED` | - Gửi trùng `client_id` cùng một `user_id` trả về bản ghi cũ.<br>- Gửi trùng `client_id` của `user_id` khác trả về `409 Conflict` (`code="client_id_taken"`). |
| **FR-COMM-003** | Xem đóng góp cá nhân | Người dùng xem danh sách các đóng góp do chính mình gửi (`GET /v1/contributions/mine`) sắp xếp theo `created_at` giảm dần. | `VERIFIED` | - Trả về đúng các bản ghi có `user_id == current_user.id`. |
| **FR-COMM-004** | Hàng đợi kiểm duyệt (Moderation Queue) | Reviewer/Admin xem danh sách đóng góp theo trạng thái (`GET /v1/contributions?status=pending`). | `PARTIAL` | - Thành viên thường (`role="member"`) gọi vào bị chặn với `403 Forbidden`.<br>- Cần bổ sung quyền cho role `admin` và hỗ trợ lọc theo `language_code`. |
| **FR-COMM-005** | Phê duyệt hoặc Từ chối đóng góp | Reviewer/Admin duyệt câu (`POST /v1/contributions/{id}/review` với `status` là `approved` hoặc `rejected` và `review_note`). | `PARTIAL` | - Cập nhật `status`, `reviewer_id`, `review_note`, `updated_at`.<br>- Cần kiểm tra quy tắc: người dùng không được tự duyệt đóng góp của chính mình trừ khi là `admin` (hoặc cấu hình cho phép trong môi trường demo). |

---

### 2.6. Offline Synchronization & Training Export (`FR-SYNC` & `FR-EXP`)

| ID | Tên yêu cầu | Mô tả chi tiết | Trạng thái | Tiêu chí nghiệm thu (Acceptance Criteria) |
| :--- | :--- | :--- | :---: | :--- |
| **FR-SYNC-001** | Đồng bộ đẩy dữ liệu (Sync Push) | Cho phép thiết bị đẩy tối đa 50 đóng góp trong một lần gọi (`POST /v1/sync/push`). Đảm bảo tính idempotent theo `client_id`. | `VERIFIED` | - Tất cả các mục hợp lệ được lưu trong một transaction và trả về danh sách trạng thái hiện tại của từng đóng góp (kể cả những đóng góp đã được duyệt trước đó). |
| **FR-SYNC-002** | Đồng bộ kéo dữ liệu (Sync Pull) | Cho phép thiết bị tải toàn bộ gói dữ liệu (`languages`, `peoples`, `heritage`, `lessons` kèm câu hỏi, và `approved_contributions`) qua `GET /v1/sync/pull`. | `PARTIAL` | - Đảm bảo trong `lessons` trả về không lộ đáp án `is_correct`, và chỉ trả về các `contributions` có `status == "approved"`.<br>- Nên hỗ trợ thêm tham số `updated_after` (optional) cho phép đồng bộ gia tăng khi dữ liệu lớn. |
| **FR-EXP-001** | Xuất dữ liệu huấn luyện AI (Training CSV Export) | Xuất các cặp câu đóng góp đã được duyệt (`status == "approved"`) ra định dạng CSV (`GET /v1/training/pairs.csv`) với các cột `source_lang,target_lang,source,target,verified`. | `PARTIAL` | - Chỉ cho phép `reviewer` và `admin` truy cập.<br>- Không xuất thông tin cá nhân (`user_id`, `email`) ra file CSV.<br>- Hỗ trợ lọc thêm theo `language_code` hoặc khoảng thời gian (`from_date`, `to_date`). |

---

## 3. Non-Functional Requirements (NFR)

| ID | Nhóm | Mô tả yêu cầu | Trạng thái | Tiêu chí nghiệm thu |
| :--- | :--- | :--- | :---: | :--- |
| **NFR-SEC-001** | Bảo mật mật khẩu | Mật khẩu phải được băm bằng thuật toán kháng GPU/ASIC (Argon2 thông qua `pwdlib[argon2]`), tuyệt đối không lưu hoặc ghi log mật khẩu dạng rõ (plain text). | `VERIFIED` | Mật khẩu lưu trong cột `users.password_hash` bắt đầu bằng `$argon2id$`. |
| **NFR-SEC-002** | Bảo mật JWT & Refresh Token | Access Token có thời hạn ngắn (mặc định 15 phút), Refresh Token có thời hạn 14 ngày. Chỉ lưu bản băm SHA-256 của `jti` trong DB, không lưu nguyên chuỗi refresh token. | `VERIFIED` | Cột `refresh_tokens.token_hash` có độ dài 64 ký tự hex (SHA-256). |
| **NFR-SEC-003** | Bảo vệ đáp án Quiz | API lấy bài học và API đồng bộ offline tuyệt đối không trả về trường `is_correct` của bảng `quiz_choices`. | `VERIFIED` | Kiểm증 qua `test_lesson_hides_answer_key` trong `tests/test_api.py`. |
| **NFR-SEC-004** | Kiểm soát File Upload | Giới hạn kích thước ảnh $\le 8\text{ MB}$, âm thanh $\le 20\text{ MB}$ và kiểm tra định dạng tệp hợp lệ để ngăn chặn tải lên tệp thực thi độc hại. | `PARTIAL` | Đã kiểm tra kích thước byte (`MAX_BYTES`, `MAX_AUDIO_BYTES`); cần bổ sung kiểm tra định dạng/content-type. |
| **NFR-REL-001** | Chịu lỗi khi ML Service ngắt kết nối | Khi ML Service quá thời gian chờ (`TimeoutException`) hoặc không hoạt động (`HTTPError`), Backend phải bắt lỗi và trả về HTTP `503 Service Unavailable` với mã lỗi rõ ràng (`ml_timeout`, `ml_unavailable`), không làm sập ứng dụng. | `VERIFIED` | Đã cài đặt trong `app/integrations/ml_client.py`. |
| **NFR-PERF-001** | Bất đồng bộ (Async I/O) | Toàn bộ kết nối cơ sở dữ liệu (`SQLAlchemy AsyncSession`) và kết nối sang ML Service (`httpx.AsyncClient`) phải thực hiện bất đồng bộ để chịu tải đồng thời cao. | `VERIFIED` | Tất cả router và DB session đều sử dụng `async/await`. |
| **NFR-DEPLOY-001** | Tương thích AWS RDS & Supabase | Hỗ trợ kết nối PostgreSQL qua SSL (`ssl=require`) và cấu hình connection pool phù hợp cho cả AWS RDS PostgreSQL trực tiếp lẫn PgBouncer/Transaction Pooler. | `PARTIAL` | Cần cho phép cấu hình `DB_SSL_MODE` và pool size linh hoạt qua biến môi trường cho AWS RDS. |

---

## 4. Quy tắc Nghiệp vụ (Business Rules)

1. **BR-01 (Tính xác thực của dữ liệu văn hóa & ngôn ngữ)**: Không tự động sinh (hallucinate) các câu ngôn ngữ dân tộc bằng AI để đưa vào kho bài học hoặc di sản. Chỉ các câu mẫu (`phrases`) có `verified = true` và các đóng góp (`contributions`) có `status = 'approved'` mới được xuất cho người học và mô hình huấn luyện.
2. **BR-02 (Quy tắc cặp ngôn ngữ đóng góp)**: Một đóng góp hợp lệ phải có ngôn ngữ nguồn và ngôn ngữ đích khác nhau (`source_lang != target_lang`), và cả 3 mã `language_code`, `source_lang`, `target_lang` đều phải tồn tại trong danh mục `languages`.
3. **BR-03 (Chính tả tiếng H'Mông Việt Nam)**: Tiếng H'Mông (`hmn`) trong hệ thống sử dụng chữ Latin phổ thông tại Việt Nam, không trộn lẫn với hệ chữ RPA hải ngoại.
4. **BR-04 (Xử lý hai lớp chữ Chăm)**: Tiếng Chăm (`cjm`) có hệ chữ truyền thống Akhar Thrah (`Cham`) và hệ phiên âm Latin trong học liệu; hệ thống phân tách rõ tác vụ OCR chữ Chăm và dịch văn bản.
5. **BR-05 (Bảo toàn văn bản nhận diện khi thiếu mô hình dịch)**: Khi người dùng gửi ảnh (OCR) hoặc giọng nói (ASR) của một ngôn ngữ dân tộc đã có bộ nhận diện chữ/giọng nói nhưng chưa có mô hình dịch máy (ML Service trả về HTTP `422`), Backend vẫn phải trả về `200 OK` kèm văn bản nhận diện được (`recognized_text`) và thông báo cảnh báo trong mảng `warnings`, thay vì trả lỗi thất bại hoàn toàn.


# 08. TESTING REQUIREMENTS & STRATEGY

> **Tài liệu:** Chiến lược Kiểm thử, Danh mục Test Cases (Unit, Integration, API, Security) và Tiêu chí Nghiệm thu  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)  
> **Đối chiếu:** `tests/conftest.py`, `tests/test_api.py`, `tests/test_scoring.py`

---

## 1. Chiến lược Kiểm thử Tổng thể (Test Strategy)

### 1.1. Nguyên tắc Kiểm thử Bắt buộc
1. **Cách ly hoàn toàn với Production Database**:
   - Toàn bộ quá trình chạy `pytest` bắt buộc sử dụng cơ sở dữ liệu cô lập (`sqlite+aiosqlite:///:memory:` được ép cứng trong `tests/conftest.py` trước khi nạp `app.main`).
   - Tuyệt đối không chạy bộ test tự động trực tiếp lên AWS RDS PostgreSQL hoặc Supabase Production.
2. **Cách ly với ML Service thực tế bằng Mock/Fake Providers**:
   - Sử dụng cơ chế `app.dependency_overrides[get_ml_client]` của FastAPI để giả lập các kịch bản phản hồi của ML Service:
     - Dịch thành công (`FakeMl`).
     - ASR nhận diện được tiếng dân tộc nhưng mô hình dịch chưa sẵn sàng (`SpeechOnlyMl` trả lỗi `422`).
     - ASR nghe tiếng H'Mông và xuất thẳng văn bản tiếng Việt (`SpeechTranslationMl`).
     - ML Service bị quá thời gian chờ (`ml_timeout`) hoặc mất kết nối (`ml_unavailable`).
3. **Kiểm chứng thực tế**:
   - Mọi thay đổi mã nguồn ở các Phase tiếp theo đều phải chạy lệnh `python -m pytest -v` thành công 100% trước khi chuyển sang bước kế tiếp.

---

## 2. Đánh giá Bộ Kiểm thử Hiện có trong Repository

Hiện tại dự án đã có **2 file test** với **8 test cases** kiểm tra các luồng cốt lõi:

| File Test | Tên hàm Test | Nhóm chức năng | Trạng thái | Nội dung kiểm tra |
| :--- | :--- | :--- | :---: | :--- |
| `tests/test_scoring.py` | `test_score_counts_only_matching_choice` | Unit Test (Scoring) | `VERIFIED` | Kiểm tra hàm `score_quiz` chấm đúng khi chọn phương án có `is_correct=True`, chấm sai khi chọn sai hoặc bỏ trống. |
| `tests/test_api.py` | `test_health_and_five_peoples` | Health & Catalog | `VERIFIED` | Kiểm tra `GET /health` trả về `"ok"`, `/v1/peoples` có đủ 5 dân tộc (`tay`, `ede`, `cham`, `hmong`, `jrai`) và `/v1/languages` có đủ 7 ngôn ngữ. |
| `tests/test_api.py` | `test_register_refresh_rotation` | Auth & Security | `VERIFIED` | Kiểm tra đăng ký, gọi `/v1/auth/me`, xoay vòng `/v1/auth/refresh` thành công lần 1 và trả về `401` khi dùng lại token cũ lần 2. |
| `tests/test_api.py` | `test_translate_text_and_image_fallback` | AI Translation & OCR | `VERIFIED` | Kiểm tra `POST /v1/translate` và `POST /v1/translate/image` trả về `recognized_text` và bản dịch. |
| `tests/test_api.py` | `test_speech_keeps_transcript_when_translation_is_not_ready` | ASR Fallback (BR-05) | `VERIFIED` | Khi ASR nhận diện được `"kuv mus tsev"` (`hmn`) nhưng mô hình dịch trả `422`, API vẫn trả `200 OK` giữ nguyên `recognized_text` và `warnings`. |
| `tests/test_api.py` | `test_speech_translation_uses_the_text_language` | Speech-to-Text ASR | `VERIFIED` | Khi checkpoint ASR nghe `hmn` nhưng trả về chữ `vi`, dịch sang `vi` không gọi lại MT, dịch sang `en` dùng `source_lang="vi"`. |
| `tests/test_api.py` | `test_lesson_hides_answer_key` | Learning & Security | `VERIFIED` | Đảm bảo `GET /v1/lessons/{id}` không chứa chuỗi `"is_correct"` và nộp bài rỗng đạt `0/3` điểm. |
| `tests/test_api.py` | `test_contribution_is_reviewed_before_training_export` | Community, RBAC, Sync, Export | `VERIFIED` | Member tạo đóng góp (`pending`), bị chặn `403` khi tải CSV; Reviewer duyệt (`approved`) và tải CSV thành công; Member `sync/push` lại cùng `client_id` nhận trạng thái `approved`. |
| `tests/test_api.py` | `test_pull_contains_catalog` | Offline Sync Pull | `VERIFIED` | Kiểm tra `GET /v1/sync/pull` trả về đủ 5 dân tộc, 5 bài học và danh sách đóng góp đã duyệt. |

---

## 3. Danh mục Test Cases Cần Bổ sung (Theo 15 Nhóm Yêu cầu)

Để đáp ứng đầy đủ Mục 9 của Master Prompt, các test cases sau cần được bổ sung trong Phase 6:

| Mã Test | Nhóm chức năng | Kịch bản kiểm thử (Test Scenario) | Kết quả kỳ vọng | Trạng thái |
| :--- | :--- | :--- | :--- | :---: |
| **TC-AUTH-01** | 1. Authentication | Đăng ký trùng email; đăng nhập sai mật khẩu; gọi `/v1/auth/logout` rồi dùng lại refresh token. | Trả về `409 email_taken`, `401 invalid_login`, và `401 unauthorized` sau khi logout. | `MISSING` |
| **TC-AUTH-02** | 2. Authorization | Dùng `refresh_token` làm Bearer token gọi `/v1/auth/me`; tài khoản `admin` truy cập hàng đợi duyệt câu và xuất CSV. | Dùng refresh token làm access token trả về `401`; `admin` gọi API kiểm duyệt trả về `200 OK`. | `MISSING` |
| **TC-USER-01** | 3. User | Đổi mật khẩu (`POST /v1/auth/change-password`) với mật khẩu cũ đúng/sai, sau đó đăng nhập bằng mật khẩu mới. | Đổi thành công, mật khẩu cũ hết hiệu lực, mật khẩu mới đăng nhập `200 OK`. | `MISSING` |
| **TC-CAT-01** | 4. Ethnic Groups | Lấy chi tiết dân tộc `/v1/peoples/tay` và dân tộc không tồn tại `/v1/peoples/unknown`; lọc/tìm kiếm dân tộc. | `/v1/peoples/tay` trả về `200` kèm `language` và `heritage`; `/v1/peoples/unknown` trả về `404`. | `MISSING` |
| **TC-CAT-02** | 5. Languages | Lấy chi tiết ngôn ngữ `/v1/languages/tyz` và mã không tồn tại `/v1/languages/xyz`; lọc theo `role`. | Trả về `200 OK` cho `tyz`, `404 Not Found` cho `xyz`. | `MISSING` |
| **TC-CAT-03** | 6. Heritage | Kiểm tra dữ liệu di sản trong `/v1/peoples/{slug}` và `/v1/heritage` (lọc theo `group_slug`, `kind`). | Trả về đúng danh sách mục di sản văn hóa tương ứng. | `MISSING` |
| **TC-TRANS-01** | 7. Translation | Dịch văn bản với mã ngôn ngữ không hợp lệ (`source_lang="xx"`); kiểm tra lưu lịch sử `GET /v1/translate/history`. | Mã ngôn ngữ lạ trả về `400 unknown_language`; lịch sử dịch lưu đúng `user_id`. | `MISSING` |
| **TC-OCR-01** | 8. OCR | Upload ảnh vượt quá giới hạn hoặc sai định dạng; ML Service trả lỗi timeout (`503`). | Trả về `413 file_too_large` / `400 invalid_file_type` / `503 ml_timeout`. | `MISSING` |
| **TC-ASR-01** | 9. ASR | Upload audio lỗi/quá dung lượng; kiểm tra xử lý lỗi khi ASR service ngắt kết nối (`503`). | Trả về `413` hoặc `503 ml_unavailable`, Backend vẫn hoạt động ổn định. | `MISSING` |
| **TC-LEARN-01** | 10. Learning | Lọc bài học theo ngôn ngữ (`GET /v1/lessons?language=tyz`), truy cập bài học không tồn tại (`404`). | Chỉ trả về bài học tiếng Tày (`tyz`); ID lạ trả về `404`. | `MISSING` |
| **TC-QUIZ-01** | 11. Quiz & Progress | Nộp đáp án đúng toàn bộ bài quiz khi đã đăng nhập và kiểm tra API tiến độ học tập (`GET /v1/lessons/progress/me`). | Đạt điểm tối đa `3/3`, bản ghi tiến độ học tập được lưu và trả về chính xác. | `MISSING` |
| **TC-COMM-01** | 12. Contribution | Gửi đóng góp có `source_lang == target_lang` hoặc `client_id` trùng với người dùng khác. | Trả về `400 same_language` và `409 client_id_taken`. | `MISSING` |
| **TC-REV-01** | 13. Reviewer Approval | Duyệt đóng góp không tồn tại (`404`), trạng thái không hợp lệ (`422`), từ chối đóng góp (`rejected`) kèm lý do. | Trả về đúng mã lỗi; đóng góp `rejected` không xuất hiện trong CSV huấn luyện. | `MISSING` |
| **TC-SYNC-01** | 14. Offline Sync | Đẩy nhiều đóng góp cùng lúc qua `/v1/sync/push` và kiểm tra `/v1/sync/pull` sau khi có đóng góp được duyệt. | `approved_contributions` trong `/v1/sync/pull` chứa đúng câu vừa được duyệt. | `MISSING` |
| **TC-EXP-01** | 15. Training Export | Lọc dữ liệu xuất CSV `/v1/training/pairs.csv?language_code=tyz` và kiểm tra không lộ dữ liệu `pending`/`rejected`. | Chỉ xuất các dòng khớp bộ lọc và có `status == "approved"`. | `MISSING` |

---

## 4. Tiêu chí Nghiệm thu Kiểm thử (Testing Acceptance Criteria)

1. Toàn bộ test hiện có và test mới trong thư mục `tests/` chạy hoàn tất với **0 failed, 0 errors**.
2. Độ bao phủ chức năng đạt **15/15 nhóm nghiệp vụ** được yêu cầu.
3. Thời gian chạy toàn bộ test suite trên SQLite in-memory dưới **10 giây**.


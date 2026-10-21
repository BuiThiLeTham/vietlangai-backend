# Backend

API điều phối người dùng, dịch, học, di sản và câu cộng đồng đóng góp. Database đích là PostgreSQL của Supabase. File `supabase/migrations/0001_init.sql` tạo bảng và RLS: anon chỉ đọc catalog, không đọc đáp án quiz, không ghi đóng góp.

Kết nối pooler cần `ssl=require` và tắt prepared statement cache. SQLite là đường chạy local khi chưa có project Supabase.

JWT access 15 phút. Refresh là JWT có `jti`, hash lưu trong bảng, dùng một lần rồi xoay. Role `reviewer` duyệt câu. CSV `GET /v1/training/pairs.csv` là đầu vào cho nhóm model.

Chạy test: `python -m pytest` trong thư mục này.

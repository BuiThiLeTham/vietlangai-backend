# Ngôn Sắc Việt (VietLangAI) – Backend API

Backend điều phối người dùng, danh mục dân tộc – ngôn ngữ – di sản văn hóa, học tập & trắc nghiệm (Quiz), dịch thuật đa phương thức (Text, Image OCR, Voice ASR), kiểm duyệt câu đóng góp cộng đồng, đồng bộ ngoại tuyến (Offline Sync) và xuất dữ liệu huấn luyện AI.

---

## 1. Công nghệ Chính

- **Framework**: Python 3.11+ & FastAPI (Async I/O)
- **Database**: PostgreSQL (AWS RDS PostgreSQL / Supabase PostgreSQL) & SQLite (Local Development / Testing)
- **ORM & Migrations**: SQLAlchemy 2.0 (`AsyncSession`) + Alembic
- **Authentication**: JWT Access Token (15 phút) + Refresh Token Rotation (SHA-256 `jti`, xoay vòng một lần) + Argon2 Password Hashing (`pwdlib`)
- **Testing**: Pytest

---

## 2. Cấu trúc Thư mục

```text
vietlangai-backend/
├── alembic/                  # Quản lý Database Migrations (Alembic Async)
├── app/
│   ├── core/                 # Cấu hình (config.py), Database (db.py), Auth/RBAC (deps.py, security.py),
│   │                         # Xử lý lỗi toàn cục (exceptions.py), Rate Limiting (rate_limit.py)
│   ├── integrations/         # HTTP Client tích hợp ML Service độc lập (ml_client.py)
│   ├── routers/              # RESTful API Routers: auth, catalog, learn, translate, community
│   ├── main.py               # Khởi tạo FastAPI, Lifespan, CORS, /health
│   ├── models.py             # SQLAlchemy 2.0 ORM Models (11 bảng)
│   ├── paths.py              # Đọc dữ liệu danh mục gốc từ shared/languages.json
│   ├── scoring.py            # Logic chấm điểm bài Quiz
│   └── seed.py               # Seed dữ liệu idempotent cho 5 dân tộc & 7 ngôn ngữ
├── docs/                     # Bộ tài liệu Requirements, Architecture & AWS Deployment Guide (01..10)
├── shared/languages.json     # Ngữ liệu chuẩn: 7 ngôn ngữ, 5 dân tộc, 5 di sản
├── supabase/migrations/      # DDL SQL và chính sách RLS cho Supabase Postgres
└── tests/                    # Bộ kiểm thử tự động Pytest
```

---

## 3. Hướng dẫn Cài đặt & Chạy Local

### 3.1. Khởi tạo môi trường ảo và cài đặt thư viện

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### 3.2. Cấu hình biến môi trường

Sao chép `.env.example` thành `.env` và điều chỉnh thông số phù hợp (mặc định nếu chưa cấu hình `DATABASE_URL`, ứng dụng sẽ dùng SQLite tại `./data/dev.db`):

```powershell
Copy-Item .env.example .env
```

### 3.3. Chạy Database Migration (Alembic)

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 3.4. Khởi động Server phát triển

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI (OpenAPI Docs)**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## 4. Chạy Kiểm thử (Pytest)

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 5. Tài liệu Kỹ thuật & Triển khai AWS

Toàn bộ tài liệu phân tích yêu cầu, thiết kế cơ sở dữ liệu, đặc tả API và hướng dẫn triển khai **AWS EC2 + AWS RDS PostgreSQL** nằm trong thư mục [`docs/`](./docs/):

1. [`docs/01_PROJECT_OVERVIEW.md`](./docs/01_PROJECT_OVERVIEW.md)
2. [`docs/02_BACKEND_REQUIREMENTS.md`](./docs/02_BACKEND_REQUIREMENTS.md)
3. [`docs/03_DATABASE_REQUIREMENTS.md`](./docs/03_DATABASE_REQUIREMENTS.md)
4. [`docs/04_API_REQUIREMENTS.md`](./docs/04_API_REQUIREMENTS.md)
5. [`docs/05_AI_INTEGRATION_REQUIREMENTS.md`](./docs/05_AI_INTEGRATION_REQUIREMENTS.md)
6. [`docs/06_SYSTEM_ARCHITECTURE.md`](./docs/06_SYSTEM_ARCHITECTURE.md)
7. [`docs/07_SECURITY_PERFORMANCE_REQUIREMENTS.md`](./docs/07_SECURITY_PERFORMANCE_REQUIREMENTS.md)
8. [`docs/08_TESTING_REQUIREMENTS.md`](./docs/08_TESTING_REQUIREMENTS.md)
9. [`docs/09_IMPLEMENTATION_ROADMAP.md`](./docs/09_IMPLEMENTATION_ROADMAP.md)
10. [`docs/10_AWS_DEPLOYMENT_GUIDE.md`](./docs/10_AWS_DEPLOYMENT_GUIDE.md)

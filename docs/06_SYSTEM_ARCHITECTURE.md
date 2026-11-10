# 06. SYSTEM ARCHITECTURE & AWS DEPLOYMENT DESIGN

> **Tài liệu:** Kiến trúc Hệ thống Backend, Luồng Dữ liệu (DFD) và Thiết kế Hạ tầng AWS EC2 + RDS PostgreSQL  
> **Phiên bản:** 1.0 (Phase 0 – Requirements & Technical Documentation)

---

## 1. Kiến trúc Phân tầng Backend (Backend Layered Architecture)

Hệ thống Backend `vietlangai-backend` được xây dựng trên nền tảng **Python 3.11+ & FastAPI** với mô hình lập trình bất đồng bộ (`async/await`) xuyên suốt từ tầng HTTP Router xuống tầng Database (`SQLAlchemy AsyncSession`) và tầng tích hợp AI (`httpx.AsyncClient`).

### 1.1. Cấu trúc Thư mục Hiện tại và Định hướng Hoàn thiện

```text
vietlangai-backend/
├── alembic/                      # [PROPOSED - Phase 2] Quản lý Database Migrations
│   ├── versions/                 # Các phiên bản migration
│   └── env.py                    # Cấu hình chạy migration với AsyncEngine
├── alembic.ini                   # [PROPOSED - Phase 2] File cấu hình Alembic
├── app/
│   ├── core/                     # Hạ tầng cốt lõi (Configuration, DB, Security, Exceptions)
│   │   ├── config.py             # [VERIFIED] Quản lý biến môi trường qua Pydantic Settings
│   │   ├── db.py                 # [VERIFIED] Khởi tạo AsyncEngine & AsyncSession
│   │   ├── deps.py               # [VERIFIED] Dependency Injection (get_db, get_current_user)
│   │   ├── security.py           # [VERIFIED] Argon2 password hashing & JWT encode/decode
│   │   └── exceptions.py         # [PROPOSED - Phase 2] Global Exception Handlers thống nhất
│   ├── integrations/             # Tích hợp dịch vụ bên ngoài
│   │   └── ml_client.py          # [VERIFIED] HTTP Client bất đồng bộ kết nối ML Service
│   ├── routers/                  # Tầng điều phối HTTP Endpoints (/v1/*)
│   │   ├── auth.py               # [VERIFIED/PARTIAL] Đăng ký, đăng nhập, refresh, logout, me
│   │   ├── catalog.py            # [VERIFIED/PARTIAL] Ngôn ngữ, dân tộc, di sản văn hóa
│   │   ├── community.py          # [VERIFIED/PARTIAL] Đóng góp, kiểm duyệt, sync, CSV export
│   │   ├── learn.py              # [VERIFIED/PARTIAL] Bài học, câu mẫu, câu hỏi & chấm quiz
│   │   └── translate.py          # [VERIFIED/PARTIAL] Dịch văn bản, OCR ảnh, ASR giọng nói
│   ├── main.py                   # [VERIFIED] Khởi tạo ứng dụng FastAPI, Lifespan, CORS, /health
│   ├── models.py                 # [VERIFIED] Định nghĩa ORM Models (SQLAlchemy 2.0)
│   ├── paths.py                  # [VERIFIED] Truy xuất đường dẫn shared/languages.json
│   ├── scoring.py                # [VERIFIED] Logic chấm điểm bài trắc nghiệm
│   └── seed.py                   # [VERIFIED] Khởi tạo dữ liệu gốc idempotent
├── docs/                         # [PHASE 0] Bộ tài liệu Requirements & Architecture
├── shared/
│   └── languages.json            # [VERIFIED] Dữ liệu gốc 7 ngôn ngữ, 5 dân tộc, 5 di sản
├── supabase/
│   └── migrations/0001_init.sql  # [VERIFIED] DDL SQL khởi tạo bảng & chính sách RLS
├── tests/                        # [VERIFIED] Bộ kiểm thử tự động Pytest
│   ├── conftest.py
│   ├── test_api.py
│   └── test_scoring.py
├── .env.example                  # [PARTIAL] Mẫu cấu hình biến môi trường
├── Dockerfile                    # [VERIFIED] Đóng gói container Python 3.11-slim
└── pyproject.toml                # [VERIFIED] Khai báo dependencies và cấu hình pytest
```

---

## 2. Sơ đồ Thành phần Hệ thống (Component Diagram)

```mermaid
flowchart TB
    subgraph ClientTier["Tầng Ứng dụng (Client Tier)"]
        Mobile["Flutter Mobile App<br/>(vietlangai-mob)"]
        LocalDB[("Local Storage / SQLite<br/>(Offline Cache & Queue)")]
        Mobile <--> LocalDB
    end

    subgraph BackendTier["Tầng Backend API (FastAPI - AWS EC2)"]
        CORS["CORS & Security Middleware"]
        subgraph Routers["API Routers (/v1)"]
            R_Auth["auth.py<br/>(/v1/auth/*)"]
            R_Cat["catalog.py<br/>(/v1/languages, /v1/peoples)"]
            R_Learn["learn.py<br/>(/v1/lessons/*)"]
            R_Trans["translate.py<br/>(/v1/translate*)"]
            R_Comm["community.py<br/>(/v1/contributions, /v1/sync, /v1/training)"]
        end
        Deps["Dependencies & RBAC<br/>(deps.py, security.py)"]
        Scoring["Quiz Scoring Engine<br/>(scoring.py)"]
        MLClient["ML Integration Client<br/>(ml_client.py)"]
        ORM["SQLAlchemy 2.0 Async ORM<br/>(db.py, models.py)"]
    end

    subgraph DataTier["Tầng Dữ liệu & AI (Data & AI Tier)"]
        RDS[("PostgreSQL Database<br/>(AWS RDS / Supabase)")]
        MLService["Independent ML Service<br/>(/v1/translate, /v1/ocr, /v1/asr)"]
        CatalogJSON["shared/languages.json<br/>(Seed Catalog)"]
    end

    Mobile ==>|"HTTPS REST API (JSON / Multipart)"| CORS
    CORS --> Routers
    Routers --> Deps
    R_Learn --> Scoring
    R_Trans --> MLClient
    MLClient ==>|"Async HTTP (httpx)"| MLService
    Routers --> ORM
    ORM ==>|"asyncpg (SSL/TLS)"| RDS
    CatalogJSON -.->|"Auto Seed on Lifespan"| ORM
```

---

## 3. Các Luồng Xử lý Chính (Key System Flows)

### 3.1. Luồng Xác thực & Xoay vòng Refresh Token (Authentication Flow)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Flutter App
    participant Auth as /v1/auth/*
    participant Sec as security.py (JWT + Argon2)
    participant DB as PostgreSQL (users, refresh_tokens)

    Client->>Auth: POST /v1/auth/login {email, password}
    Auth->>DB: SELECT * FROM users WHERE email = lower(email)
    DB-->>Auth: User record
    Auth->>Sec: verify_password(password, user.password_hash)
    Sec-->>Auth: True
    Auth->>Sec: create_access_token(user.id) [TTL: 15m]
    Auth->>Sec: create_refresh_token(user.id) [TTL: 14d, sinh jti ngẫu nhiên]
    Auth->>DB: INSERT INTO refresh_tokens (user_id, sha256(jti), expires_at)
    Auth-->>Client: 200 OK {access_token, refresh_token, expires_in: 900}

    Note over Client,DB: Khi Access Token hết hạn sau 15 phút:
    Client->>Auth: POST /v1/auth/refresh {refresh_token}
    Auth->>Sec: Giải mã JWT, kiểm tra typ=="refresh", băm sha256(jti)
    Auth->>DB: SELECT * FROM refresh_tokens WHERE token_hash = digest
    alt Token hợp lệ, chưa hết hạn và revoked_at IS NULL
        Auth->>DB: UPDATE refresh_tokens SET revoked_at = now()
        Auth->>Sec: Sinh cặp access_token & refresh_token mới
        Auth->>DB: INSERT refresh_token mới
        Auth-->>Client: 200 OK {access_token mới, refresh_token mới}
    else Token đã bị dùng trước đó hoặc hết hạn
        Auth-->>Client: 401 Unauthorized
    end
```

---

### 3.2. Luồng Đồng bộ Ngoại tuyến & Kiểm duyệt Cộng đồng (Offline Sync & Moderation Flow)

```mermaid
sequenceDiagram
    autonumber
    actor Member as Mobile User (Offline -> Online)
    participant Sync as /v1/sync/* & /v1/contributions
    participant DB as PostgreSQL
    actor Reviewer as Reviewer / Admin

    Note over Member: 1. Tải dữ liệu về dùng Offline
    Member->>Sync: GET /v1/sync/pull
    Sync->>DB: Truy vấn languages, peoples, heritage, lessons, approved_contributions
    Sync-->>Member: 200 OK (Gói dữ liệu Offline, ẩn đáp án quiz)

    Note over Member: 2. Người dùng tạo câu đóng góp khi mất mạng (lưu kèm client_id trên máy)
    Member->>Sync: POST /v1/sync/push {contributions: [{client_id: "dev-001", ...}]}
    loop Với mỗi đóng góp trong danh sách (tối đa 50)
        Sync->>DB: Kiểm tra SELECT * FROM contributions WHERE client_id = "dev-001"
        alt Chưa tồn tại
            Sync->>DB: INSERT INTO contributions (status = "pending")
        else Đã tồn tại và cùng user_id
            Sync->>DB: Giữ nguyên bản ghi hiện có (Idempotent)
        end
    end
    Sync-->>Member: 200 OK {contributions: [...]}

    Note over Reviewer: 3. Kiểm duyệt và Xuất dữ liệu huấn luyện
    Reviewer->>Sync: GET /v1/contributions?status=pending
    Sync-->>Reviewer: Danh sách câu chờ duyệt
    Reviewer->>Sync: POST /v1/contributions/{id}/review {status: "approved", review_note: "..."}
    Sync->>DB: UPDATE contributions SET status="approved", reviewer_id=..., updated_at=now()
    Reviewer->>Sync: GET /v1/training/pairs.csv
    Sync->>DB: SELECT * FROM contributions WHERE status="approved"
    Sync-->>Reviewer: 200 OK (File CSV: source_lang,target_lang,source,target,verified)
```

---

## 4. Kiến trúc Triển khai AWS EC2 & AWS RDS PostgreSQL

Hệ thống hướng tới triển khai Production trên hạ tầng **AWS VPC** đảm bảo tính bảo mật mạng và khả năng phục hồi dữ liệu:

```mermaid
flowchart LR
    subgraph Internet["Internet"]
        Users["Flutter Mobile App / Reviewers"]
    end

    subgraph VPC["AWS VPC (ap-southeast-1)"]
        subgraph PublicSubnet["Public Subnet"]
            EC2["AWS EC2 Instance<br/>Nginx Reverse Proxy (443/80)<br/>+ Docker / Systemd Gunicorn-Uvicorn<br/>(FastAPI Port 8000)"]
        end

        subgraph PrivateSubnet["Private Subnet (Isolated)"]
            RDS[("AWS RDS PostgreSQL<br/>Port 5432<br/>Encrypted & Automated Backups")]
            MLHost["ML Service Instance (EC2 GPU/CPU)<br/>Port 8100"]
        end
    end

    Users ==>|"HTTPS (TLS 1.2/1.3)"| EC2
    EC2 ==>|"Security Group SG-DB (TCP 5432, SSL)"| RDS
    EC2 ==>|"Security Group SG-ML (TCP 8100)"| MLHost
```

### 4.1. Thiết kế Bảo mật Hạ tầng AWS
1. **Phân tách Subnet**:
   - **AWS EC2 (Backend API)** đặt tại Public Subnet, chỉ mở cổng `80` (chuyển hướng HTTPS) và `443` (HTTPS qua Nginx/Certbot hoặc ALB) ra Internet; cổng `22` (SSH) chỉ giới hạn cho IP quản trị hoặc dùng AWS Systems Manager Session Manager.
   - **AWS RDS PostgreSQL** đặt tại **Private Subnet** (`Publicly Accessible = No`).
2. **Thiết kế Security Groups**:
   - `sg-vietlangai-ec2`: Inbound `443/tcp` từ `0.0.0.0/0`; Outbound tới RDS và ML Service.
   - `sg-vietlangai-rds`: Inbound `5432/tcp` **chỉ cho phép nguồn là `sg-vietlangai-ec2`**, từ chối mọi kết nối trực tiếp từ Internet.
3. **Kết nối Cơ sở dữ liệu (`app/core/db.py`)**:
   - Sử dụng biến môi trường `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<rds-endpoint>:5432/<dbname>`.
   - Kết nối mã hóa SSL (`ssl="require"`). Lưu ý: Hiện tại `app/core/db.py` đang đặt cứng `statement_cache_size: 0` để phục vụ Supabase Transaction Pooler; khi kết nối trực tiếp tới AWS RDS PostgreSQL (không qua PgBouncer transaction mode), có thể giữ `statement_cache_size: 0` (vẫn tương thích 100% với RDS) hoặc cho phép cấu hình qua biến môi trường.
4. **Sao lưu và Phục hồi (Backup & Recovery)**:
   - Kích hoạt **Automated Backups** trên AWS RDS (retention tối thiểu 7 ngày) và chụp **Final Snapshot** trước khi thực hiện bất kỳ thao tác nâng cấp schema lớn nào bằng Alembic.


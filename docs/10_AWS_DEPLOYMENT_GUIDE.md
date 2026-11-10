# 10. AWS EC2 & RDS POSTGRESQL DEPLOYMENT GUIDE

> **Tài liệu:** Hướng dẫn Triển khai Production trên AWS EC2 và AWS RDS PostgreSQL  
> **Phiên bản:** 1.0 (Phase 7 – AWS Deployment Preparation)

---

## 1. Kiến trúc Triển khai trên AWS

- **Compute**: AWS EC2 (`Ubuntu 24.04 LTS`, `t3.small` hoặc `t3.medium`) đặt tại **Public Subnet**, chạy FastAPI qua Docker hoặc `systemd` + `uvicorn` sau lớp **Nginx Reverse Proxy** (HTTPS/TLS).
- **Database**: AWS RDS for PostgreSQL (PostgreSQL 15/16, `db.t4g.micro` hoặc `db.t4g.small`) đặt tại **Private Subnet**, không mở public IP ra ngoài Internet.
- **AI / ML Service**: Chạy trên instance riêng trong VPC (hoặc container nội bộ) giao tiếp với Backend qua biến môi trường `ML_BASE_URL`.

---

## 2. Thiết lập AWS RDS PostgreSQL

1. **Khởi tạo RDS Instance**:
   - Engine: **PostgreSQL 16**.
   - Subnet Group: Chọn các **Private Subnets** trong VPC.
   - Public access: **No** (Tuyệt đối không mở port `5432` ra `0.0.0.0/0`).
   - VPC Security Group (`sg-vietlangai-rds`):
     - Inbound Rule: Type `PostgreSQL`, Protocol `TCP`, Port `5432`, Source: `sg-vietlangai-ec2` (Security Group của EC2 Backend).
   - Backup: Bật **Automated backups** (Retention: `7 days`) và bật **Storage encryption**.
2. **Chuỗi kết nối (`DATABASE_URL`)**:
   ```env
   DATABASE_URL=postgresql+asyncpg://vietlang_admin:YOUR_STRONG_PASSWORD@vietlangai-rds.xxxx.ap-southeast-1.rds.amazonaws.com:5432/vietlangai
   DB_SSL_REQUIRE=true
   DB_STATEMENT_CACHE_SIZE=0
   DB_POOL_SIZE=10
   DB_MAX_OVERFLOW=20
   ```

---

## 3. Thiết lập AWS EC2 & Triển khai Ứng dụng

### 3.1. Cấu hình Security Group cho EC2 (`sg-vietlangai-ec2`)
- Inbound `80/tcp` (HTTP) từ `0.0.0.0/0` (chuyển hướng sang HTTPS).
- Inbound `443/tcp` (HTTPS) từ `0.0.0.0/0`.
- Inbound `22/tcp` (SSH) chỉ từ IP cố định của quản trị viên.

### 3.2. Cài đặt và Chạy Migration bằng Alembic
Trên máy chủ EC2 (sau khi clone repository và tạo file `.env` từ `.env.example`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .

# Kiểm tra phiên bản migration hiện tại và nâng cấp schema trên RDS
alembic upgrade head
```

### 3.3. Phương án A: Chạy bằng Docker (Khuyên dùng)

`Dockerfile` đã bao gồm đầy đủ `app/`, `shared/languages.json`, `alembic/` và `alembic.ini`:

```bash
docker build -t vietlangai-backend:latest .
docker run -d \
  --name vietlangai-api \
  --restart unless-stopped \
  --env-file .env \
  -p 127.0.0.1:8000:8000 \
  vietlangai-backend:latest
```

### 3.4. Phương án B: Chạy bằng `systemd` Service

Tạo file `/etc/systemd/system/vietlangai.service`:

```ini
[Unit]
Description=VietLangAI FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/vietlangai-backend
EnvironmentFile=/opt/vietlangai-backend/.env
ExecStart=/opt/vietlangai-backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Kích hoạt dịch vụ:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vietlangai
sudo systemctl status vietlangai
```

---

## 4. Cấu hình Nginx Reverse Proxy & HTTPS

Tạo file `/etc/nginx/sites-available/vietlangai`:

```nginx
server {
    listen 80;
    server_name api.ngonsacviet.vn;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 190s;
    }
}
```

Cài đặt chứng chỉ SSL Let's Encrypt:
```bash
sudo ln -s /etc/nginx/sites-available/vietlangai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.ngonsacviet.vn
```

---

## 5. Kiểm tra Vận hành (Health Check & Smoke Test)

```bash
curl -s https://api.ngonsacviet.vn/health
# Kỳ vọng: {"status":"ok","service":"api","database":"ok"}
```


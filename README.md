# Nền tảng Học tập Nguyễn Văn Huyên

Một nền tảng học tập và luyện thi toàn diện được xây dựng bằng Django và PostgreSQL, tích hợp các công cụ hỗ trợ bởi AI (thông qua OpenAI/Google GenAI) và khả năng tìm kiếm vector với `pgvector`.

## Các Module Chính
- **`accounts`**: Quản lý người dùng, xác thực và hồ sơ.
- **`classes`**: Quản lý lớp học và học sinh.
- **`exams`**: Quản lý ngân hàng câu hỏi, tạo bài thi, và chấm điểm.
- **`docs`**: Xử lý và quản lý tài liệu học tập.
- **`ai_core`**: Tích hợp AI (OpenAI/Gemini) để nhúng văn bản (text embedding), tạo câu hỏi và xây dựng lộ trình học tập.
- **`onthi12`**: Module chuyên biệt hỗ trợ luyện thi khối 12.
- **`notifications`**: Hệ thống thông báo đa luồng theo thời gian thực cho người dùng.

## Yêu cầu Hệ thống (Prerequisites)
- **Python**: 3.12+
- **PostgreSQL**: 15+ (BẮT BUỘC phải cài đặt sẵn extension `pgvector`). Hoặc có thể sử dụng giải pháp Docker ở môi trường Local.

---

## Hướng dẫn Cài đặt Chi tiết 

### 1. Clone Repository (Tải mã nguồn)
```bash
git clone <repository-url>
cd onthi12
```

### 2. Thiết lập Môi trường Ảo (Virtual Environment)
Tạo môi trường Python biệt lập để quản lý các package của dự án:
```bash
python -m venv .venv
```

Kích hoạt môi trường ảo vừa tạo:
- **Trên Windows (Command Prompt / PowerShell)**:
  ```powershell
  .venv\Scripts\activate
  ```
- **Trên macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### 3. Cài đặt thư viện (Dependencies)
Cài đặt toàn bộ các thư viện cần thiết đã được liệt kê trong file `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường (`.env`)
Tạo một file có tên `.env` tại thư mục gốc (nơi chứa file `manage.py`) và điền các thông tin sau. Lưu ý: Tuyệt đối không commit file này lên Git để bảo mật.

**Nội dung mẫu file `.env`**:
```env
DEBUG=True
SECRET_KEY='your-secure-random-secret-key' # Thay đổi thành một chuỗi bảo mật ngẫu nhiên

# Cấu hình PostgreSQL (Local)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=nvhlearningdb
DB_USER=admindb
DB_PASSWORD=Admin@123
DB_HOST=localhost
DB_PORT=5432

# Tích hợp AI (Bắt buộc)
AI_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key # API key lấy từ OpenAI Dashboard
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

# Tùy chọn vận hành
# CACHE_BACKEND=db                 # Mặc định locmem; dùng db cần bảng django_cache_table
# CRON_SECRET=your-cron-secret     # Bảo vệ endpoint cron thông báo trên Vercel
# AI_INSIGHT_COOLDOWN_DAYS=5       # Số ngày giữa 2 lần tạo báo cáo AI Insight
CLOUDINARY_CLOUD_NAME=your-cloud
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Nếu hệ thống sử dụng NeonDB (Môi trường Staging/Prod) hoặc cloud database khác:
# DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'
```

> [!IMPORTANT]
> **Lưu ý về biến `DEBUG`:**
> - **`DEBUG=True`**: Sử dụng khi đang lập trình tại local (Development). Django sẽ hiển thị chi tiết log lỗi trên giao diện để dễ dàng debug.
> - **`DEBUG=False`**: **Bắt buộc** phải điều chỉnh khi làm môi trường thực tế (Production/Vercel) để bảo mật hệ thống, tránh lộ mã nguồn và các truy vấn nhạy cảm ra ngoài.


### 5. Thiết lập Cơ sở dữ liệu Local (Sử dụng Docker)
Nếu bạn chưa cài đặt PostgreSQL với `pgvector` trên máy, thuận tiện nhất là sử dụng Docker (yêu cầu Docker Engine đang khởi chạy):

```bash
docker run --name nvh_postgres \
  -e POSTGRES_DB=nvhlearningdb \
  -e POSTGRES_USER=admindb \
  -e POSTGRES_PASSWORD=Admin@123 \
  -p 5432:5432 \
  -d pgvector/pgvector:pg15
```
*Lưu ý: Đảm bảo các thông tin User, Password, DB_NAME ở trên khớp với cấu hình trong file `.env`.*

### 6. Cập nhật cấu trúc Cơ sở dữ liệu (Migrations)
Tạo các bảng theo schema đã định nghĩa:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Tạo tài khoản Quản trị cấp cao (Superuser)
Tạo một tài khoản Quản trị để có thể truy cập vào trang Admin của Django quản trị chuyên sâu dự án:
```bash
python manage.py createsuperuser
```
*(Bạn sẽ được yêu cầu nhập Tên đăng nhập, Email định dạng và Mật khẩu).*

### 8. Phân phối Static Files (Tùy chọn Local - Bắt buộc trên Production)
Tổng hợp lại tất cả các file tĩnh (HTML, CSS, JS, ảnh) vào thư mục `STATIC_ROOT` để Django và web server có thể render:
```bash
python manage.py collectstatic
```
*(Gõ "yes" nếu được hỏi về việc ghi đè file).*

### 9. Khởi động Web Server (Development)
Chạy development server cục bộ để thao tác và kiểm thử giao diện:
```bash
python manage.py runserver
```
🌍 Nền tảng sẽ chạy và có thể truy cập tại địa chỉ: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## Triển khai (Deployment Lên Vercel)

Dự án này đã được đóng gói và cấu hình để có thể lập tức triển khai chuẩn theo kiến trúc serverless trên nền tảng **Vercel** bằng Python 3.12 runtime.

1. Bạn có thể cài đặt Vercel CLI để deploy trực tiếp hoặc cấu hình kết nối trực tiếp repository từ Dashboard của Vercel web.
2. Dự án sử dụng file `vercel.json` để thực hiện việc định tuyến (routing) tệp WSGI và cấu hình dung lượng memory (max lambda size).
3. Trong quá trình Build (Build phase) trên platform của họ, Vercel sẽ tự động sử dụng script `build.sh` đã được cấu hình với nhiệm vụ cài đặt các dependency và tự động chạy `collectstatic`.
4. Đảm bảo tất cả các khóa bí mật của bạn trong file `.env` đã được nhập vào thẻ cài đặt **Environment Variables** bảo mật trên Vercel dashboard.
5. Thay đổi dự án và chạy dòng lệnh sau (cần có Vercel CLI):
   ```bash
   vercel --prod
   ```

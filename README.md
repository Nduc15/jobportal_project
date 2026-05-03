# JobPortal AI - Hệ thống Tuyển dụng Tích hợp AI

Dự án cổng thông tin việc làm hiện đại, hỗ trợ ứng viên tạo CV Online và giúp nhà tuyển dụng phân tích mức độ phù hợp của ứng viên bằng công nghệ AI (Google Gemini).

## 🚀 Các tính năng chính
- **Dành cho Ứng viên:** Tìm kiếm việc làm, Lưu tin, Tạo CV Online chuyên nghiệp, Theo dõi lịch phỏng vấn.
- **Dành cho Nhà tuyển dụng:** Đăng tin tuyển dụng, Quản lý ứng viên, **AI Matching** (Tự động phân tích điểm kỹ năng, kinh nghiệm và gợi ý câu hỏi phỏng vấn).
- **Hệ thống lịch hẹn:** Đặt lịch phỏng vấn trực tuyến/trực tiếp và thông báo ngay trên Dashboard.

---

## 🛠 Hướng dẫn cài đặt

Để chạy dự án này trên máy cục bộ, vui lòng làm theo các bước sau:

### 1. Tải mã nguồn
```bash
git clone https://github.com/Nduc15/jobportal_project.git
cd jobportal_project
```

### 2. Tạo môi trường ảo (Khuyến nghị)
```bash
# Windows
python -m venv env
.\env\Scripts\activate

# macOS/Linux
python3 -m venv env
source env/bin/activate
```

### 3. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường
1. Copy tệp `.env.example` thành tệp `.env`:
   ```bash
   cp .env.example .env
   ```
2. Mở tệp `.env` và điền **Gemini API Key** của bạn. 
   > Bạn có thể lấy Key miễn phí tại: [Google AI Studio](https://aistudio.google.com/app/apikey)

### 5. Khởi tạo Cơ sở dữ liệu
```bash
python manage.py migrate
```

### 6. Tạo tài khoản Admin (Để duyệt tin tuyển dụng)
```bash
python manage.py createsuperuser
```

### 7. Chạy server
```bash
python manage.py runserver
```
Truy cập: `http://127.0.0.1:8000/`

---

## 📝 Lưu ý quan trọng
- **AI Matching:** Chỉ hoạt động khi bạn cung cấp đúng `GEMINI_API_KEY` trong tệp `.env`. Nếu không, hệ thống sẽ sử dụng logic tính toán thủ công làm dự phòng.
- **File CV:** Tính năng AI hiện tại tối ưu nhất cho các ứng viên sử dụng chức năng **Tạo CV Online** của hệ thống.

---

## 📞 Liên hệ
Nếu có bất kỳ câu hỏi nào, vui lòng liên hệ qua GitHub Issues của dự án.

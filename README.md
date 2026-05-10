# Luan Pro Video Editor & Translator 🚀

**Phần mềm chỉnh sửa và dịch thuật video tự động bằng AI chuyên nghiệp.**

Đây là công cụ hỗ trợ re-up video từ các nền tảng nước ngoài (Douyin, Youtube, TikTok...) sang tiếng Việt một cách hoàn toàn tự động chỉ với 1 cú click.

## 🌟 Tính năng nổi bật

- **Auto 1-Click Pipeline**: Quy trình tự động từ A-Z (Lấy phụ đề -> Dịch thuật -> Tạo giọng đọc AI -> Render video).
- **AI Translation**: Hỗ trợ các model mạnh mẽ nhất hiện nay: Gemini 3 Flash Preview, GPT-4o, Claude 3.5 Sonnet.
- **Speech-to-Text**: Trích xuất phụ đề cực nhanh bằng Faster-Whisper (Offline) hoặc Gemini API.
- **Giọng đọc AI**: Tích hợp giọng đọc tự nhiên (Nam/Nữ) với tốc độ tùy chỉnh.
- **Chỉnh sửa video**:
    - Tự động vẽ vùng che phụ đề cũ.
    - Chèn Logo cá nhân dễ dàng.
    - Hỗ trợ xuất nhiều định dạng cùng lúc (9:16, 16:9, 1:1, Gốc).
    - Hiệu ứng chữ Karaoke hiện đại.
    - Auto Ducking: Tự động lọc/giảm âm lượng nhạc nền khi có giọng đọc AI.
    - Lật video (Mirror) ngang/dọc để tránh bản quyền.

## 🛠 Cài đặt

1. **Yêu cầu hệ thống**:
    - Python 3.8 trở lên.
    - FFmpeg (Đã được tích hợp sẵn trong code).

2. **Cài đặt thư viện**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Cấu hình API Key**:
    - Mở ứng dụng, vào tab **"Cài đặt"**.
    - Nhập API Key của Gemini, OpenAI hoặc Claude.
    - Nhấn **"Lưu cài đặt"**.

## 📖 Hướng dẫn sử dụng (Auto 1-Click)

1. **Bước 1 (Dự án)**: Chọn thư mục để lưu các video sau khi xử lý.
2. **Bước 2 (Video)**: Chọn file video gốc cần dịch.
3. **Bước 3 (Cấu hình)**:
    - Chọn phương thức lấy phụ đề (Khuyên dùng: Faster-Whisper).
    - Chọn model AI để dịch (Mặc định: Gemini 3 Flash Preview).
    - Chọn định dạng video đầu ra (TikTok, Youtube...).
4. **Bước 4 (Tùy chọn)**: 
    - Chọn Logo (nếu có).
    - Tùy chỉnh màu sắc, cỡ chữ phụ đề.
    - Tick "Chữ Karaoke" để có hiệu ứng chữ chạy.
5. **Bắt đầu**: Nhấn **"🚀 CHẠY TOÀN BỘ"** và đợi trong giây lát.

## ⚙️ Cài đặt mặc định

Phần mềm đã được tối ưu sẵn các thiết lập:
- Model dịch: **Gemini 3 Flash Preview**.
- Tự động lọc giọng gốc để chèn giọng đọc AI rõ hơn.
- Giao diện tối (Dark Mode) hiện đại, dễ sử dụng.

## 📝 Lưu ý

- File `.env` dùng để lưu API Key, không nên chia sẻ file này.
- Thư mục dự án sẽ được tự động ghi nhớ cho các lần sử dụng sau.

---
*Phát triển bởi luanhua8888-dev*

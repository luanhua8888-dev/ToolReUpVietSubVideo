import os
import re
import requests
import yt_dlp
import subprocess
import imageio_ffmpeg

def get_douyin_no_watermark(url):
    """
    Sử dụng API TikWM (Miễn phí) để lấy link Douyin không logo.
    """
    try:
        # Hỗ trợ cả link v.douyin.com và douyin.com/video/ID
        api_url = "https://www.tikwm.com/api/"
        data = {"url": url, "hd": 1}
        response = requests.post(api_url, data=data).json()
        
        if response.get("code") == 0:
            video_data = response.get("data")
            # Ưu tiên bản HD không watermark
            return video_data.get("hdplay") or video_data.get("play")
    except Exception as e:
        print(f"[-] Lỗi parsing Douyin No Watermark: {e}")
    return None

def download_video(url, output_dir, progress_callback=None):
    """
    Tự động nhận diện và tải video từ Bilibili, Douyin, Youtube...
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "downloaded_source.%(ext)s")
    
    # 1. Xử lý đặc biệt cho Douyin (No Watermark)
    if "douyin.com" in url or "tiktok.com" in url:
        if progress_callback: progress_callback("[*] Đang lấy link Douyin không hình mờ (No Watermark)...")
        no_wm_url = get_douyin_no_watermark(url)
        if no_wm_url:
            if progress_callback: progress_callback("[+] Đã tìm thấy link chất lượng cao. Đang tải...")
            target_file = os.path.join(output_dir, "downloaded_source.mp4")
            
            # Tải file bằng requests để có progress (hoặc dùng yt-dlp với link trực tiếp)
            response = requests.get(no_wm_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 * 1024 # 1MB
            
            downloaded = 0
            with open(target_file, 'wb') as f:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    f.write(data)
                    if progress_callback and total_size > 0:
                        pct = int(downloaded / total_size * 100)
                        progress_callback(f"Đang tải Douyin: {pct}%")
            return target_file

    # 2. Mặc định dùng yt-dlp cho Bilibili, Youtube, và fallback Douyin
    if progress_callback: progress_callback(f"[*] Đang tải video bằng yt-dlp: {url}")
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.bilibili.com/', # Quan trọng cho Bilibili
        'ffmpeg_location': ffmpeg_path, # Chỉ định đường dẫn FFmpeg
    }
    
    # Thêm cookies nếu có (Bilibili cần cookies để tải HD)
    cookie_file = "cookies.txt"
    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        if progress_callback: progress_callback(f"[-] Lỗi tải bằng yt-dlp: {e}")
        return None

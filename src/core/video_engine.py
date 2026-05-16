import os
import subprocess
import shutil
import cv2
import imageio_ffmpeg
import audio_maker
import translate
import pysrt
from src.utils import downloader
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class VideoEngine:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def update_progress(self, msg, pct=None):
        if self.progress_callback:
            self.progress_callback(msg, pct)

    def process_full_pipeline(self, input_source, options):
        """
        Quy trình xử lý toàn diện: Tải -> STT -> Dịch -> TTS -> Render
        """
        temp_dir = "_web_output"
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        # 1. Tải video nếu là link
        video_path = input_source
        if input_source.startswith("http"):
            self.update_progress("Đang tải video từ link...", 0.05)
            video_path = downloader.download_video(input_source, temp_dir)
            if not video_path:
                return None, "Lỗi tải video"

        # 2. STT (Tạm thời dùng Gemini API cho nhanh và nhẹ)
        self.update_progress("Đang nhận diện giọng nói (STT)...", 0.15)
        srt_path = os.path.join(temp_dir, "source.srt")
        
        # Logic trích xuất audio và STT
        audio_temp = os.path.join(temp_dir, "temp_audio.mp3")
        subprocess.run([self.ffmpeg_exe, "-y", "-i", video_path, "-vn", "-c:a", "libmp3lame", audio_temp], capture_output=True)
        
        api_key = options.get('gemini_key') or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None, "Thiếu Gemini API Key"
        
        genai.configure(api_key=api_key)
        audio_file = genai.upload_file(path=audio_temp)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "Please transcribe this audio and return ONLY a properly formatted SRT file."
        response = model.generate_content([prompt, audio_file])
        
        srt_content = response.text.strip()
        if srt_content.startswith("```"):
            srt_content = "\n".join(srt_content.split("\n")[1:-1])
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # 3. Dịch thuật
        self.update_progress("Đang dịch thuật...", 0.4)
        vi_srt_path = os.path.join(temp_dir, "vi.srt")
        translated_content = translate.translate_full_srt(
            srt_content, 
            model_name=options.get('translate_model', 'gemini-1.5-flash'),
            context=options.get('context', '')
        )
        with open(vi_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_content)

        # 4. Render Video
        self.update_progress("Đang lồng tiếng & Render...", 0.6)
        output_path = os.path.join(temp_dir, "final_output.mp4")
        
        # (Ở đây tích hợp render logic từ gui.py - rút gọn cho web)
        # Tạm thời gọi lại render_video cơ bản
        result = self.render_video_advanced(video_path, vi_srt_path, output_path, options)
        
        return result, None

    def render_video_advanced(self, video_path, srt_path, output_path, options):
        # Trích xuất thông tin video
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_ms = int((frame_count / fps) * 1000)
        vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        temp_dir = os.path.dirname(output_path)
        tts_audio = os.path.join(temp_dir, "tts_audio.wav")
        synced_srt = os.path.join(temp_dir, "synced.srt")

        # TTS
        audio_maker.generate_tts_track(
            srt_path, duration_ms, tts_audio, 
            voice=options.get('voice', 'vi-VN-HoaiMyNeural'),
            speed=options.get('speed', '+0%'),
            output_srt_path=synced_srt
        )

        # FFmpeg Render
        cmd = [self.ffmpeg_exe, "-y", "-i", video_path, "-i", tts_audio]
        
        # Simple Filter: Overlay TTS and Subtitles
        # Note: In a real app, we'd add crop/blur logic here
        filter_str = f"[0:v]subtitles='{synced_srt.replace('\\', '/')}'[v_out];[1:a]volume=1.2[a_out]"
        
        cmd.extend(["-filter_complex", filter_str, "-map", "[v_out]", "-map", "[a_out]", output_path])
        subprocess.run(cmd, capture_output=True)
        
        return output_path

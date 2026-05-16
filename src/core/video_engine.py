import os
import subprocess
import shutil
import cv2
import imageio_ffmpeg
import audio_maker
import translate
import pysrt
import re
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
        temp_dir = "_web_output"
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)
        
        video_path = input_source
        if isinstance(input_source, str) and input_source.startswith("http"):
            self.update_progress("Đang tải video từ link...", 0.05)
            video_path = downloader.download_video(input_source, temp_dir)
        
        if not video_path or not os.path.exists(video_path):
            return None, "Không tìm thấy video nguồn"

        # 1. STT
        self.update_progress("Đang nhận diện giọng nói (STT)...", 0.15)
        srt_path = os.path.join(temp_dir, "source.srt")
        audio_temp = os.path.join(temp_dir, "temp_audio.mp3")
        subprocess.run([self.ffmpeg_exe, "-y", "-i", video_path, "-vn", "-c:a", "libmp3lame", audio_temp], capture_output=True)
        
        api_key = options.get('gemini_key') or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        audio_file = genai.upload_file(path=audio_temp)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(["Transcribe to SRT", audio_file])
        
        srt_content = response.text.strip()
        if srt_content.startswith("```"): srt_content = "\n".join(srt_content.split("\n")[1:-1])
        with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)

        # 2. Dịch
        self.update_progress("Đang dịch thuật AI...", 0.4)
        vi_srt_path = os.path.join(temp_dir, "vi.srt")
        translated = translate.translate_full_srt(srt_content, model_name="gemini-1.5-flash", context=options.get('context', ''))
        with open(vi_srt_path, "w", encoding="utf-8") as f: f.write(translated)

        # 3. Render
        self.update_progress("Đang Render Video (Full Filters)...", 0.6)
        output_path = os.path.join(temp_dir, "final_output.mp4")
        result = self.render_video_advanced(video_path, vi_srt_path, output_path, options)
        
        return result, None

    def render_video_advanced(self, video_path, srt_path, output_path, options):
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration_ms = int((frame_count / (fps or 30)) * 1000)
        vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        temp_dir = os.path.dirname(output_path)
        tts_audio = os.path.join(temp_dir, "tts_audio.wav")
        synced_srt = os.path.join(temp_dir, "synced.srt")

        # Generate TTS
        audio_maker.generate_tts_track(
            srt_path, duration_ms, tts_audio, 
            voice=options.get('voice', 'vi-VN-HoaiMyNeural'),
            speed=options.get('speed', '+0%'),
            output_srt_path=synced_srt
        )

        # Build Filter Complex (Advanced)
        filters = []
        v_in = "[0:v]"
        
        # Mirror
        if options.get('mirror_h'): 
            filters.append(f"{v_in}hflip[vflip_h]")
            v_in = "[vflip_h]"
        if options.get('mirror_v'):
            filters.append(f"{v_in}vflip[vflip_v]")
            v_in = "[vflip_v]"
            
        # Subtitles
        # We use the ass filter for better styling (karaoke if possible)
        # But for simplicity, we use subtitles filter
        escaped_srt = synced_srt.replace('\\', '/').replace(':', '\\:')
        filters.append(f"{v_in}subtitles='{escaped_srt}'[v_sub]")
        v_in = "[v_sub]"

        # Audio Mix (Ducking)
        bg_vol = options.get('bg_vol', 0.6)
        duck_depth = options.get('duck_depth', 0.5)
        # Simplified ducking: [0:a]bg + [1:a]tts
        filters.append(f"[0:a]volume={bg_vol}[a_bg];[1:a]volume=1.2[a_tts];[a_bg][a_tts]amix=inputs=2:duration=first[a_out]")

        filter_complex = ";".join(filters)
        
        cmd = [self.ffmpeg_exe, "-y", "-i", video_path, "-i", tts_audio]
        cmd.extend(["-filter_complex", filter_complex, "-map", v_in, "-map", "[a_out]", output_path])
        
        subprocess.run(cmd, capture_output=True)
        return output_path

import os
import subprocess
import pysrt
import numpy as np
import soundfile as sf
import imageio_ffmpeg
import concurrent.futures

def time_to_ms(t):
    return (t.hours * 3600 + t.minutes * 60 + t.seconds) * 1000 + t.milliseconds

def trim_silence(audio_data, threshold=0.01):
    non_silent_indices = np.where(np.abs(audio_data) > threshold)[0]
    if len(non_silent_indices) == 0:
        return audio_data
    start_idx = non_silent_indices[0]
    end_idx = non_silent_indices[-1]
    
    pad = int(24000 * 0.05) # 0.05s padding
    start_idx = max(0, start_idx - pad)
    end_idx = min(len(audio_data), end_idx + pad)
    return audio_data[start_idx:end_idx]

def process_single_sub(idx, text, start_ms, max_duration_ms, voice, speed, sr, ffmpeg_exe):
    import sys
    import time
    import re
    
    temp_mp3 = f"temp_tts_{idx}.mp3"
    temp_wav = f"temp_tts_{idx}.wav"
    
    # 1. Dọn dẹp text để AI đọc tự nhiên hơn
    clean_text = re.sub(r'[\[\(].*?[\]\)]', '', text)
    clean_text = clean_text.replace('-', ' ').replace('~', ' ').strip()
    if not clean_text:
        return idx, start_ms, None, temp_mp3, temp_wav
    
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--rate", speed,
        "--text", clean_text,
        "--write-media", temp_mp3
    ]
    
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NO_WINDOW
        
    data = None
    
    # 2. Thử lại tối đa 3 lần nếu lỗi
    for attempt in range(3):
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
        
        if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
            subprocess.run([ffmpeg_exe, "-y", "-i", temp_mp3, "-ar", str(sr), "-ac", "1", temp_wav], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
            if os.path.exists(temp_wav):
                try:
                    data, _ = sf.read(temp_wav)
                    if len(data.shape) > 1: data = np.mean(data, axis=1)
                    
                    data = trim_silence(data)
                    actual_duration_ms = len(data) / sr * 1000
                    
                    # 3. ÉP TỐC ĐỘ (ATEMPO) NẾU GIỌNG ĐỌC QUÁ DÀI
                    if actual_duration_ms > max_duration_ms and max_duration_ms > 0:
                        ratio = actual_duration_ms / max_duration_ms
                        if ratio > 100: ratio = 100
                        
                        filter_str = f"atempo={ratio}"
                        if ratio > 2.0:
                            filter_str = f"atempo=2.0,atempo={ratio/2.0}"
                            if ratio > 4.0:
                                filter_str = f"atempo=2.0,atempo=2.0,atempo={ratio/4.0}"
                                
                        temp_fast_wav = f"temp_fast_{idx}.wav"
                        sf.write(temp_wav, data, sr) # Ghi lại bản đã trim
                        subprocess.run([ffmpeg_exe, "-y", "-i", temp_wav, "-filter:a", filter_str, "-ar", str(sr), "-ac", "1", temp_fast_wav], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
                        
                        if os.path.exists(temp_fast_wav):
                            data_fast, _ = sf.read(temp_fast_wav)
                            if len(data_fast.shape) > 1: data_fast = np.mean(data_fast, axis=1)
                            data = data_fast
                            os.remove(temp_fast_wav)
                            
                    break # Thành công thì thoát
                except:
                    pass
        
        if os.path.exists(temp_mp3):
            try: os.remove(temp_mp3)
            except: pass
        time.sleep(1)
                
    return idx, start_ms, data, temp_mp3, temp_wav


def generate_tts_track(srt_path, video_duration_ms, output_path, update_callback=None, voice="vi-VN-HoaiMyNeural", speed="+0%", preview_duration=0, output_srt_path=None):
    """
    Sử dụng Đa luồng (Multi-threading) để tải cực nhanh.
    """
    try:
        subs = pysrt.open(srt_path)
    except:
        subs = pysrt.open(srt_path, encoding='utf-8')
        
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    sr = 24000
    
    total_samples = int(video_duration_ms / 1000.0 * sr)
    master_audio = np.zeros(total_samples, dtype=np.float32)
    
    total_subs = len(subs)
    temp_files = []
    tasks = []
    
    for i, sub in enumerate(subs):
        text = sub.text.replace('\n', ' ')
        start_ms = time_to_ms(sub.start)
        if preview_duration > 0 and start_ms > preview_duration * 1000:
            continue
            
        if i < len(subs) - 1:
            next_start = time_to_ms(subs[i+1].start)
            max_dur = next_start - start_ms - 50 # Chừa 50ms khoảng cách
            if max_dur < 100: max_dur = 100
        else:
            max_dur = time_to_ms(sub.end) - start_ms + 2000
            
        tasks.append((i, text, start_ms, max_dur))
        
    completed = 0
    results = []
    # Xử lý song song 5 luồng cùng lúc
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_single_sub, t[0], t[1], t[2], t[3], voice, speed, sr, ffmpeg_exe): t for t in tasks}
        
        for future in concurrent.futures.as_completed(futures):
            idx, start_ms, data, f1, f2 = future.result()
            temp_files.extend([f1, f2])
            
            if data is not None:
                results.append((start_ms, data, idx))
            
            completed += 1
            if update_callback and completed % 5 == 0:
                update_callback(f"Đang xử lý thần tốc Giọng đọc AI: {completed}/{total_subs}", completed / max(1, total_subs))

    if update_callback:
        update_callback("Đang ráp nối và xử lý chống chồng âm thanh (No Overlap)...", 1.0)
        
    # Sắp xếp các đoạn theo thời gian
    results.sort(key=lambda x: x[0])
    
    current_sample = 0
    for start_ms, data, idx in results:
        start_sample = int(start_ms / 1000.0 * sr)
        
        # Bắt buộc bắt đầu đúng lúc chữ xuất hiện
        if start_sample < current_sample:
            start_sample = current_sample
            
        end_sample = start_sample + len(data)
        
        if start_sample < total_samples:
            if end_sample > total_samples:
                data = data[:(total_samples - start_sample)]
                end_sample = total_samples
                
            master_audio[start_sample:end_sample] = data
            
        # --- ĐỒNG BỘ TEXT VỚI ÂM THANH (KHỚP KHUNG HÌNH 100%) ---
        # Chữ sẽ xuất hiện đúng khung hình (start.ordinal không đổi)
        # Chữ sẽ biến mất ngay khi AI đọc xong (end.ordinal = end_sample)
        subs[idx].end.ordinal = int(end_sample / sr * 1000)
            
        current_sample = end_sample
        
    # Sắp xếp lại subs theo thời gian bắt đầu
    subs.sort()
    
    # NGĂN CHẶN XẾP CHỒNG (NO-OVERLAP SUBTITLES):
    # Đảm bảo câu trước kết thúc TRƯỚC HOẶC BẰNG khi câu sau bắt đầu
    for i in range(len(subs) - 1):
        if subs[i].end.ordinal >= subs[i+1].start.ordinal:
            subs[i].end.ordinal = subs[i+1].start.ordinal - 1
            
    # Chuẩn hóa (Normalize)
    max_val = np.max(np.abs(master_audio))
    if max_val > 1.0:
        master_audio = master_audio / max_val
        
    sf.write(output_path, master_audio, sr)
    
    # Dọn dẹp background
    for f in temp_files:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass
            
    # Lưu file SRT đã đồng bộ khớp hoàn toàn với Voice
    if output_srt_path:
        subs.save(output_srt_path, encoding='utf-8')
                
    return True

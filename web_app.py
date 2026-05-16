import streamlit as st
import os
import shutil
from dotenv import load_dotenv
from src.core.video_engine import VideoEngine
import time

# Load environment
load_dotenv()

# --- UI SETUP ---
st.set_page_config(page_title="Luan Pro Mobile", page_icon="📱", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e1e1e;
        border-radius: 5px 5px 0 0;
        gap: 1px;
        padding-top: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 Luan Pro Video AI (Full Features)")

# --- STATE MANAGEMENT ---
if 'blur_boxes' not in st.session_state: st.session_state.blur_boxes = []

# --- SIDEBAR: CONFIG ---
with st.sidebar:
    st.header("🔑 Cấu hình API")
    gemini_key = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
    openai_key = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    claude_key = st.text_input("Claude API Key", value=os.getenv("CLAUDE_API_KEY", ""), type="password")
    groq_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    
    st.divider()
    st.header("🎨 Định dạng mặc định")
    font_size = st.number_input("Cỡ chữ phụ đề", min_value=10, max_value=50, value=24)
    font_color = st.selectbox("Màu chữ", ["Trắng", "Vàng", "Xanh lá", "Đỏ"])
    
# --- MAIN PANEL ---
tab_auto, tab_settings, tab_preview = st.tabs(["🚀 Auto 1-Click", "⚙️ Cài đặt nâng cao", "👁️ Xem trước & Vẽ"])

with tab_auto:
    col_input, col_config = st.columns([1, 1])
    
    with col_input:
        st.markdown("### 📥 Đầu vào")
        video_url = st.text_input("Link video (Douyin, YT...)", placeholder="https://...")
        uploaded_video = st.file_uploader("Tải video lên", type=["mp4", "mov", "mkv"])
        
        st.markdown("### 🖼️ Logo & Hình ảnh")
        uploaded_logo = st.file_uploader("Tải Logo (PNG/JPG)", type=["png", "jpg"])
        logo_size = st.select_slider("Cỡ Logo", options=["Nhỏ", "Vừa", "To"], value="Vừa")
        
    with col_config:
        st.markdown("### 📝 Phụ đề & Dịch")
        stt_source = st.selectbox("Nguồn phụ đề", ["Từ Âm Thanh (Whisper Offline)", "Từ Âm Thanh (Gemini API)", "File SRT có sẵn"])
        if stt_source == "File SRT có sẵn":
            uploaded_srt = st.file_uploader("Chọn file SRT", type=["srt"])
            
        trans_model = st.selectbox("Model AI Dịch", [
            "Gemini 3 Flash Preview", "Gemini 2.0 Flash", "GPT-4o", "Claude 3.5 Sonnet", "Groq Llama 3"
        ])
        trans_context = st.text_input("Ngữ cảnh dịch (Xưng hô...)", placeholder="Ví dụ: Xưng tôi và bạn...")

        st.markdown("### 🎙️ Giọng đọc AI")
        voice_choice = st.selectbox("Chọn giọng", ["Nữ (Hoài My)", "Nam (Nam Minh)"])
        voice_speed = st.select_slider("Tốc độ đọc", options=["-20%", "-10%", "Bình thường", "+10%", "+20%"], value="Bình thường")
        bg_vol = st.slider("Âm lượng nền", 0.0, 1.5, 0.6)
        duck_depth = st.slider("Độ dìm nhạc (Ducking)", 0.0, 1.0, 0.5)

with tab_settings:
    st.markdown("### 🛠️ Tùy chọn nâng cao")
    c1, c2 = st.columns(2)
    with c1:
        chk_vocal_remove = st.checkbox("Lọc bỏ giọng gốc (Giữ tiếng môi trường)", value=True)
        chk_karaoke = st.checkbox("Hiệu ứng chữ Karaoke", value=True)
        chk_sub_bg = st.checkbox("Nền cho phụ đề", value=False)
        chk_thumbnail = st.checkbox("Tự tạo ảnh bìa (Thumbnail)", value=True)
    with c2:
        chk_mirror_h = st.checkbox("Lật ngang video", value=False)
        chk_mirror_v = st.checkbox("Lật dọc video", value=False)
        chk_preview_60s = st.checkbox("Chỉ xuất bản nháp 60s", value=False)
        chk_mute_orig = st.checkbox("Tắt hoàn toàn tiếng gốc", value=False)

    st.markdown("### 📐 Xuất khung hình (Chọn nhiều)")
    formats = st.multiselect("Định dạng đầu ra", 
                            ["Gốc", "Dọc 9:16 (TikTok)", "Ngang 16:9 (Youtube)", "Vuông 1:1"],
                            default=["Gốc"])

with tab_preview:
    st.info("💡 Tính năng vẽ vùng mờ trực tiếp đang được tối ưu cho di động. Hiện tại bạn có thể xem video gốc tại đây.")
    if uploaded_video:
        st.video(uploaded_video)
    elif video_url:
        st.write(f"Video từ link: {video_url}")
    else:
        st.write("Chưa có video để xem trước.")

# --- EXECUTION ---
st.divider()
if st.button("🚀 CHẠY TOÀN BỘ TIẾN TRÌNH", type="primary", use_container_width=True):
    if not uploaded_video and not video_url:
        st.error("❌ Bạn chưa cung cấp video đầu vào!")
    else:
        status = st.empty()
        progress = st.progress(0)
        
        def update_ui(msg, pct):
            status.info(f"⏳ {msg}")
            if pct is not None: progress.progress(pct)

        engine = VideoEngine(progress_callback=update_ui)
        
        # Prepare options
        opt = {
            'gemini_key': gemini_key,
            'translate_model': trans_model,
            'context': trans_context,
            'voice': "vi-VN-NamMinhNeural" if "Nam" in voice_choice else "vi-VN-HoaiMyNeural",
            'speed': "+0%" if voice_speed == "Bình thường" else voice_speed,
            'formats': formats,
            'vocal_remove': chk_vocal_remove,
            'karaoke': chk_karaoke,
            'mirror_h': chk_mirror_h,
            'mirror_v': chk_mirror_v,
            'bg_vol': bg_vol,
            'duck_depth': duck_depth
        }
        
        # ... logic gọi engine ...
        st.warning("Đang kết nối các module xử lý nâng cao. Vui lòng giữ trình duyệt mở.")
        # result, error = engine.process_full_pipeline(...)
        time.sleep(2)
        st.success("Tính năng đang được hoàn thiện phần render phức tạp. Bạn có thể sử dụng các tùy chọn cơ bản trước.")

st.caption("Phiên bản Web Full Features v1.1 - Luan Pro")

import streamlit as st
import os
import shutil
from dotenv import load_dotenv
from src.core.video_engine import VideoEngine
import time

# Load environment
load_dotenv()

# --- UI SETUP ---
st.set_page_config(page_title="Luan Pro Mobile", page_icon="📱", layout="centered")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: white;
    }
    .big-button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        font-size: 20px !important;
        padding: 20px !important;
        border-radius: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 Luan Pro Video AI")
st.write("Dịch & Lồng tiếng video ngay trên điện thoại của bạn.")

# --- SIDEBAR: CONFIG ---
with st.sidebar:
    st.header("🔑 Cấu hình")
    gemini_key = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
    groq_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    st.info("API Key được dùng để dịch thuật và nhận diện giọng nói.")

# --- INPUT SECTION ---
tab1, tab2 = st.tabs(["🔗 Dán Link", "📤 Tải Video"])

with tab1:
    video_url = st.text_input("Nhập link (Douyin, Bilibili, Youtube...)", placeholder="https://v.douyin.com/...")

with tab2:
    uploaded_file = st.file_uploader("Chọn video từ máy", type=["mp4", "mov", "mkv"])

# --- SETTINGS ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    model_choice = st.selectbox("Model AI", ["Gemini 1.5 Flash", "Gemini 1.5 Pro", "Groq Llama 3"])
    voice_choice = st.selectbox("Giọng đọc", ["Nữ (Hoài My)", "Nam (Nam Minh)"])

with col2:
    format_choice = st.selectbox("Định dạng", ["Gốc", "TikTok (9:16)", "Youtube (16:9)", "Vuông (1:1)"])
    speed_choice = st.select_slider("Tốc độ", options=["-10%", "Bình thường", "+10%"], value="Bình thường")

# --- ACTION ---
if st.button("🚀 BẮT ĐẦU XỬ LÝ", use_container_width=True):
    if not uploaded_file and not video_url:
        st.error("⚠️ Vui lòng chọn video hoặc dán link!")
    else:
        status_container = st.empty()
        progress_bar = st.progress(0)
        
        def progress_cb(msg, pct):
            status_container.info(f"⏳ {msg}")
            if pct is not None:
                progress_bar.progress(pct)

        engine = VideoEngine(progress_callback=progress_cb)
        
        input_source = ""
        if uploaded_file:
            input_source = "temp_input.mp4"
            with open(input_source, "wb") as f:
                f.write(uploaded_file.getbuffer())
        else:
            input_source = video_url

        # Options map
        options = {
            'gemini_key': gemini_key,
            'translate_model': "gemini-1.5-flash",
            'voice': "vi-VN-NamMinhNeural" if "Nam" in voice_choice else "vi-VN-HoaiMyNeural",
            'speed': "+0%" if speed_choice == "Bình thường" else speed_choice,
            'format': format_choice
        }

        try:
            result_path, error = engine.process_full_pipeline(input_source, options)
            
            if error:
                st.error(f"❌ Lỗi: {error}")
            else:
                st.success("✅ Đã xử lý xong!")
                st.video(result_path)
                with open(result_path, "rb") as f:
                    st.download_button("📥 TẢI VIDEO VỀ ĐIỆN THOẠI", f, file_name="luan_pro_output.mp4")
        except Exception as e:
            st.error(f"💥 Lỗi hệ thống: {str(e)}")

st.divider()
st.caption("Lưu ý: Máy tính của bạn phải đang bật và chạy script này để điện thoại có thể truy cập.")

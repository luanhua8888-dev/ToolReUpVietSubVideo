import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import sys
import os
import subprocess
import imageio_ffmpeg
import cv2
import shutil
from PIL import Image, ImageTk
import re
import translate
from dotenv import load_dotenv

# Load môi trường ngay từ đầu
load_dotenv()

try:
    import audio_maker
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue")  

class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.line_count = 0
        
    def write(self, string):
        self.text_widget.after(0, self._write, string)
        
    def _write(self, string):
        if '\r' in string:
            parts = string.split('\r')
            valid_part = [p for p in parts if p.strip()]
            if valid_part:
                self.text_widget.delete("end-2l", "end-1c")
                self.text_widget.insert("end", "\n" + valid_part[-1])
        else:
            self.text_widget.insert("end", string)
            self.line_count += string.count('\n')
            
        # Chống tràn RAM / Đơ GUI khi log quá dài
        if self.line_count > 1000:
            self.text_widget.delete("1.0", "500.0")
            self.line_count -= 500
            
        self.text_widget.see("end")
        
    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Luan Pro Video Editor & Translator")
        self.geometry("1450x850")
        self.configure(fg_color="#121212")

        # Layout: 2 cột (Trái: Controls, Phải: Preview)
        self.grid_columnconfigure(0, weight=0, minsize=550)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ====== CỘT TRÁI: BẢNG ĐIỀU KHIỂN ======
        self.left_frame = ctk.CTkFrame(self, fg_color="#121212")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_frame.grid_rowconfigure(2, weight=1)

        self.tabview = ctk.CTkTabview(self.left_frame, height=450, corner_radius=10, fg_color="#1e1e1e", segmented_button_selected_color="#1f538d")
        self.tabview.grid(row=0, column=0, sticky="ew")
        
        self.tabview.add("Auto 1-Click")
        self.tabview.add("Cài đặt")

        # ====== KHỞI TẠO BIẾN DÙNG CHUNG ======
        self.model_mapping = {
            "Gemini 3 Flash Preview": "gemini-3-flash-preview",
            "Gemini 2.5 Flash": "gemini-2.5-flash",
            "Gemini 2.0 Flash": "gemini-2.0-flash",
            "Gemini 1.5 Pro Latest": "gemini-pro-latest",
            "Gemini 1.5 Flash Latest": "gemini-flash-latest",
            "OpenAI GPT-4o": "gpt-4o",
            "OpenAI GPT-4o Mini": "gpt-4o-mini",
            "Claude 3.5 Sonnet": "claude-3-5-sonnet-20240620",
            "Claude 3 Opus": "claude-3-opus-20240229"
        }
        
        self.crop_format_var = ctk.StringVar(value="Giữ nguyên gốc")
        self.font_size_var = ctk.StringVar(value="10")
        self.font_color_var = ctk.StringVar(value="Trắng")
        self.logo_size_var = ctk.StringVar(value="Vừa")
        self.chk_mirror_var = ctk.BooleanVar(value=False)
        self.chk_mirror_v_var = ctk.BooleanVar(value=False)
        self.chk_tts_var = ctk.BooleanVar(value=True)
        self.chk_mute_var = ctk.BooleanVar(value=False)
        self.voice_var = ctk.StringVar(value="Nam (Nam Minh)")
        self.speed_var = ctk.StringVar(value="Bình thường")
        self.bg_vol_var = ctk.DoubleVar(value=0.6)
        self.duck_depth_var = ctk.DoubleVar(value=0.5)
        
        self.trans_context_var = ctk.StringVar()
        self.ex_chk_auto_translate_var = ctk.BooleanVar(value=True)
        self.auto_chk_vocal_remove_var = ctk.BooleanVar(value=True)
        self.proj_dir_var = ctk.StringVar(value=os.path.join(os.path.expanduser("~"), "Videos", "LuanPro_Projects"))


        # --- TAB AUTO 1-CLICK ---
        auto_tab = self.tabview.tab("Auto 1-Click")
        
        auto_frame = ctk.CTkFrame(auto_tab, fg_color="#252525", corner_radius=8)
        auto_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # B1: Chọn Video
        b1 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b1.pack(fill="x", pady=2)
        self.auto_btn_video = ctk.CTkButton(b1, text="🎬 B1: Chọn Video", command=self.select_video, font=ctk.CTkFont(weight="bold"), width=160)
        self.auto_btn_video.pack(side="left", padx=10)
        self.auto_lbl_video = ctk.CTkLabel(b1, text="Chưa chọn", text_color="#A0A0A0")
        self.auto_lbl_video.pack(side="left", padx=5)
        
        # Thư mục chứa Dự Án
        b0 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b0.pack(fill="x", pady=(10, 2))
        ctk.CTkLabel(b0, text="📁 Thư mục lưu Dự Án:", font=ctk.CTkFont(weight="bold"), width=150, anchor="w").pack(side="left", padx=10)
        ctk.CTkEntry(b0, textvariable=self.proj_dir_var, width=280).pack(side="left", padx=5)
        ctk.CTkButton(b0, text="Chọn", width=60, command=self.select_proj_dir).pack(side="left", padx=5)

        # B2: Lấy SRT & Dịch
        b2 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b2.pack(fill="x", pady=2)
        ctk.CTkLabel(b2, text="📝 B2: Lấy SRT", font=ctk.CTkFont(weight="bold"), width=95, anchor="w").pack(side="left", padx=10)
        
        self.auto_src_var = ctk.StringVar(value="Từ Âm Thanh (Whisper Offline)")
        ctk.CTkComboBox(b2, values=["Từ Âm Thanh (Whisper Offline)", "Từ Âm Thanh (Gemini API)", "Phụ đề gốc", "File SRT có sẵn"], variable=self.auto_src_var, width=220, command=self.on_auto_src_change).pack(side="left", padx=5)
        
        self.btn_auto_select_srt = ctk.CTkButton(b2, text="📂 Chọn file", width=80, fg_color="#3498db", hover_color="#2980b9", command=self.select_auto_srt)
        # Will be packed in on_auto_src_change if selected
        
        self.lbl_auto_srt_path = ctk.CTkLabel(b2, text="", text_color="#00e676")
        
        self.auto_chk_extract_var = ctk.BooleanVar(value=True)
        self.chk_auto_trans = ctk.CTkCheckBox(b2, text="Dịch bằng:", variable=self.auto_chk_extract_var, text_color="#00e676", width=80)
        self.chk_auto_trans.pack(side="left", padx=10)
        
        self.auto_trans_model_var = ctk.StringVar(value="Gemini 3 Flash Preview")
        self.cb_auto_trans_model = ctk.CTkComboBox(b2, values=list(self.model_mapping.keys()), variable=self.auto_trans_model_var, width=200)
        self.cb_auto_trans_model.pack(side="left", padx=0)
        
        self.auto_context_var = ctk.StringVar()
        self.entry_auto_context = ctk.CTkEntry(b2, textvariable=self.auto_context_var, placeholder_text="Ngữ cảnh dịch (Xưng hô...)", width=180)
        self.entry_auto_context.pack(side="left", padx=10)
        
        # B3: Định dạng
        b3_preview = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b3_preview.pack(fill="x", pady=2)
        ctk.CTkLabel(b3_preview, text="👁️ Xem Trước Khung Hình:", font=ctk.CTkFont(weight="bold"), width=155, anchor="w").pack(side="left", padx=10)
        ctk.CTkComboBox(b3_preview, values=["Giữ nguyên gốc", "Dọc 9:16 (TikTok, Reels)", "Ngang 16:9 (Youtube, Facebook)", "Vuông 1:1 (Instagram)"], variable=self.crop_format_var, command=self.on_format_change, width=220).pack(side="left", padx=5)

        self.auto_format_goc = ctk.BooleanVar(value=True)
        self.auto_format_tiktok = ctk.BooleanVar(value=False)
        self.auto_format_youtube = ctk.BooleanVar(value=False)
        self.auto_format_vuong = ctk.BooleanVar(value=False)
        
        b3 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b3.pack(fill="x", pady=2)
        ctk.CTkLabel(b3, text="📐 B3: Xuất Khung Hình:", font=ctk.CTkFont(weight="bold"), width=155, anchor="w").pack(side="left", padx=10)
        ctk.CTkCheckBox(b3, text="Gốc", variable=self.auto_format_goc, width=50).pack(side="left", padx=5)
        ctk.CTkCheckBox(b3, text="9:16", variable=self.auto_format_tiktok, width=50).pack(side="left", padx=5)
        ctk.CTkCheckBox(b3, text="16:9", variable=self.auto_format_youtube, width=50).pack(side="left", padx=5)
        ctk.CTkCheckBox(b3, text="1:1", variable=self.auto_format_vuong, width=50).pack(side="left", padx=5)

        # B4: Logo
        b4 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        b4.pack(fill="x", pady=2)
        self.auto_btn_logo = ctk.CTkButton(b4, text="🖼️ B4: Logo (Tùy chọn)", command=self.select_logo, font=ctk.CTkFont(weight="bold"), width=160)
        self.auto_btn_logo.pack(side="left", padx=10)
        self.auto_lbl_logo = ctk.CTkLabel(b4, text="Chưa chọn", text_color="#A0A0A0")
        self.auto_lbl_logo.pack(side="left", padx=5)
        
        lbl_hint = ctk.CTkLabel(auto_frame, text="*Vẽ vùng che phụ đề cũ & Kéo Logo trực tiếp bên màn hình Preview", text_color="#FF9900", font=ctk.CTkFont(size=11, slant="italic"))
        lbl_hint.pack(pady=0)

        # Cấu hình Giao diện (Style)
        s_frame = ctk.CTkFrame(auto_frame, fg_color="#1a252c", corner_radius=8)
        s_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(s_frame, text="🎨 Cỡ chữ:", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
        ctk.CTkComboBox(s_frame, values=[str(i) for i in range(10, 40, 2)], variable=self.font_size_var, width=65, height=24, command=self.on_style_change).pack(side="left", padx=2)
        
        ctk.CTkLabel(s_frame, text="Màu:", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
        ctk.CTkComboBox(s_frame, values=["Trắng", "Vàng", "Xanh lá", "Đỏ"], variable=self.font_color_var, width=80, height=24, command=self.on_style_change).pack(side="left", padx=2)
        
        ctk.CTkLabel(s_frame, text="Cỡ Logo:", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
        ctk.CTkComboBox(s_frame, values=["Nhỏ", "Vừa", "To"], variable=self.logo_size_var, width=70, height=24, command=self.on_style_change).pack(side="left", padx=2)

        # Cấu hình nhanh Audio
        q_frame = ctk.CTkFrame(auto_frame, fg_color="#1a252c", corner_radius=8)
        q_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(q_frame, text="🎙️ Đọc AI:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=5, pady=2)
        ctk.CTkComboBox(q_frame, values=["Nữ (Hoài My)", "Nam (Nam Minh)"], variable=self.voice_var, width=130, height=24).grid(row=0, column=1, padx=2, pady=2)
        
        ctk.CTkLabel(q_frame, text="Tốc độ:", font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=5, pady=2)
        ctk.CTkComboBox(q_frame, values=["-20%", "-10%", "Bình thường", "+10%", "+20%", "+30%"], variable=self.speed_var, width=90, height=24).grid(row=0, column=3, padx=2, pady=2)

        ctk.CTkLabel(q_frame, text="🔊 Vol Nền:", font=ctk.CTkFont(size=12)).grid(row=0, column=4, padx=5, pady=2)
        ctk.CTkSlider(q_frame, from_=0, to=1.5, variable=self.bg_vol_var, width=80, height=16).grid(row=0, column=5, padx=2, pady=2)

        ctk.CTkLabel(q_frame, text="📉 Ducking:", font=ctk.CTkFont(size=12)).grid(row=0, column=6, padx=5, pady=2)
        ctk.CTkSlider(q_frame, from_=0, to=1.0, variable=self.duck_depth_var, width=80, height=16).grid(row=0, column=7, padx=2, pady=2)

        # Tùy chọn bổ sung (Sắp xếp gọn gàng thành 2 dòng)
        opt_container = ctk.CTkFrame(auto_frame, fg_color="transparent")
        opt_container.pack(fill="x", padx=15, pady=5)
        
        # Dòng 1: Cấu hình Phụ đề
        row1 = ctk.CTkFrame(opt_container, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        
        self.auto_chk_karaoke_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row1, text="🎤 Chữ Karaoke", variable=self.auto_chk_karaoke_var, text_color="#00FFCC", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 15))
        
        self.auto_chk_sub_bg_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row1, text="⬛ Nền phụ đề", variable=self.auto_chk_sub_bg_var, text_color="#AAAAAA", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
        
        self.auto_sub_bg_color_var = ctk.StringVar(value="Đen")
        ctk.CTkComboBox(row1, values=["Đen", "Xanh dương", "Đỏ", "Xám", "Vàng"], variable=self.auto_sub_bg_color_var, width=110, height=24, font=ctk.CTkFont(size=11)).pack(side="left", padx=5)
        
        self.auto_sub_opacity_var = ctk.IntVar(value=160)
        ctk.CTkLabel(row1, text="Độ đậm:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))
        ctk.CTkSlider(row1, from_=0, to=255, variable=self.auto_sub_opacity_var, width=120, height=16).pack(side="left", padx=5)

        # Dòng 2: Cấu hình Video & Render
        row2 = ctk.CTkFrame(opt_container, fg_color="transparent")
        row2.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(row2, text="🔇 Lọc giọng gốc", variable=self.auto_chk_vocal_remove_var, text_color="#FF99CC", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 15))
        
        ctk.CTkCheckBox(row2, text="🔇 Tắt tiếng gốc", variable=self.chk_mute_var, text_color="#e74c3c", font=ctk.CTkFont(size=12)).pack(side="left", padx=10)
        
        self.auto_chk_thumbnail_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, text="🖼️ Tự tạo Ảnh bìa", variable=self.auto_chk_thumbnail_var, text_color="#FFD700", font=ctk.CTkFont(size=12)).pack(side="left", padx=15)
        
        ctk.CTkCheckBox(row2, text="↔️ Lật Ngang", variable=self.chk_mirror_var, text_color="#00e676", font=ctk.CTkFont(size=12), command=self.on_format_change).pack(side="left", padx=10)
        ctk.CTkCheckBox(row2, text="↕️ Lật Dọc", variable=self.chk_mirror_v_var, text_color="#00e676", font=ctk.CTkFont(size=12), command=self.on_format_change).pack(side="left", padx=10)
        
        self.auto_chk_preview_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, text="⚡ Bản nháp 60s", variable=self.auto_chk_preview_var, text_color="#f39c12", font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=5)
        
        # Nút START AUTO và STOP
        btn_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_auto_run = ctk.CTkButton(btn_frame, text="🚀 CHẠY TOÀN BỘ", command=self.start_auto_flow, height=45, fg_color="#e74c3c", hover_color="#c0392b", font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_auto_run.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_stop_render = ctk.CTkButton(btn_frame, text="⛔ DỪNG LẠI", command=self.stop_rendering, height=45, fg_color="#7f8c8d", hover_color="#95a5a6", font=ctk.CTkFont(size=16, weight="bold"), state="disabled")
        self.btn_stop_render.pack(side="left", fill="x", expand=True, padx=(5, 5))
        
        self.btn_auto_open_folder = ctk.CTkButton(btn_frame, text="📂 MỞ THƯ MỤC", command=self.open_proj_folder, height=45, fg_color="#2ecc71", hover_color="#27ae60", font=ctk.CTkFont(size=14, weight="bold"))
        # self.btn_auto_open_folder will be packed when done
        
        self.btn_open_video = ctk.CTkButton(btn_frame, text="▶ XEM KẾT QUẢ", command=self.open_video_file, height=45, fg_color="#2ecc71", hover_color="#27ae60", font=ctk.CTkFont(size=14, weight="bold"), text_color="black")
        # Will be packed in run_video_burn

        # --- TAB CÀI ĐẶT ---
        settings_tab = self.tabview.tab("Cài đặt")
        settings_frame = ctk.CTkFrame(settings_tab, fg_color="#252525", corner_radius=8)
        settings_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(settings_frame, text="🔑 Cấu hình API Keys", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00FFCC").pack(pady=(20, 10))

        # Gemini
        ctk.CTkLabel(settings_frame, text="Gemini API Key:").pack(pady=(10, 0))
        self.gemini_key_var = ctk.StringVar(value=os.getenv("GEMINI_API_KEY", ""))
        self.gemini_key_entry = ctk.CTkEntry(settings_frame, textvariable=self.gemini_key_var, width=450, placeholder_text="AIzaSy...")
        self.gemini_key_entry.pack(pady=5)

        # OpenAI
        ctk.CTkLabel(settings_frame, text="OpenAI API Key:").pack(pady=(10, 0))
        self.openai_key_var = ctk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self.openai_key_entry = ctk.CTkEntry(settings_frame, textvariable=self.openai_key_var, width=450, placeholder_text="sk-...")
        self.openai_key_entry.pack(pady=5)

        # Claude
        ctk.CTkLabel(settings_frame, text="Claude API Key:").pack(pady=(10, 0))
        self.claude_key_var = ctk.StringVar(value=os.getenv("CLAUDE_API_KEY", ""))
        self.claude_key_entry = ctk.CTkEntry(settings_frame, textvariable=self.claude_key_var, width=450, placeholder_text="sk-ant-...")
        self.claude_key_entry.pack(pady=5)

        self.btn_save_settings = ctk.CTkButton(settings_frame, text="💾 LƯU CÀI ĐẶT", command=self.save_settings, fg_color="#2ecc71", hover_color="#27ae60", font=ctk.CTkFont(weight="bold"))
        self.btn_save_settings.pack(pady=30)


        self.progress_label = ctk.CTkLabel(self.left_frame, text="Tiến trình: 0%", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00FFCC")
        self.progress_label.grid(row=1, column=0, sticky="w", padx=10, pady=(10, 0))

        self.progress_bar = ctk.CTkProgressBar(self.left_frame, height=15, progress_color="#00FFCC", border_width=1, border_color="#2c3e50")
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 15))
        self.progress_bar.set(0)
        
        # Load Config
        self.load_config()

        self.log_textbox = ctk.CTkTextbox(self.left_frame, state="normal", font=ctk.CTkFont(family="Consolas", size=12), wrap="word", fg_color="#0f0f0f", text_color="#A0A0A0")
        self.log_textbox.grid(row=3, column=0, sticky="nsew", pady=(0, 10))

        sys.stdout = StdoutRedirector(self.log_textbox)
        sys.stderr = sys.stdout

        # ====== CỘT PHẢI: PREVIEW CANVAS ======
        self.right_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        
        top_bar = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(top_bar, text="MÀN HÌNH PREVIEW (Kéo Logo & Vẽ Vùng Mờ tại đây)", font=ctk.CTkFont(weight="bold", size=16), text_color="#00FFCC").pack(side="left")
        ctk.CTkButton(top_bar, text="⏪ Xóa Vùng Mờ Vừa Vẽ", command=self.undo_box, fg_color="#e67e22", hover_color="#d35400", width=150).pack(side="right")

        self.canvas_frame = ctk.CTkFrame(self.right_frame, fg_color="#000000")
        self.canvas_frame.pack(expand=True, fill="both", padx=15, pady=(0, 15))
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#000000", highlightthickness=0, cursor="cross")
        self.canvas.pack(expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        # Thêm phím tắt CTRL + Z để Undo
        self.bind("<Control-z>", self.undo_box)
        self.bind("<Control-Z>", self.undo_box)

        # --- Variables ---
        self.video_file = ""
        self.vi_srt_file = ""
        self.logo_file = ""
        self.output_video_path = ""
        self.video_duration = 1.0
        
        self.blur_boxes = [] # (x, y, w, h) based on orig_w, orig_h
        self.format_states = {}
        self.last_preview_fmt = "Giữ nguyên gốc"
        self.rects = []
        self.current_rect = None
        self.logo_pos = None # (x, y) based on orig_w, orig_h
        self.logo_item = None
        self.dragging_logo = False
        self.scale = 1.0
        
        self.orig_w = 0
        self.orig_h = 0
        self.vid_w = 0 # uncropped
        self.vid_h = 0 # uncropped
        
        self.raw_frame = None

        print("██╗     ██╗   ██╗ █████╗ ███╗   ██╗    ██████╗ ██████╗  ██████╗ \n██║     ██║   ██║██╔══██╗████╗  ██║    ██╔══██╗██╔══██╗██╔═══██╗\n██║     ██║   ██║███████║██╔██╗ ██║    ██████╔╝██████╔╝██║   ██║\n██║     ██║   ██║██╔══██║██║╚██╗██║    ██╔═══╝ ██╔══██╗██║   ██║\n███████╗╚██████╔╝██║  ██║██║ ╚████║    ██║     ██║  ██║╚██████╔╝\n╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝ \n")
        print("[+] Luan Pro Video Editor đã sẵn sàng.\n")

    def select_proj_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.proj_dir_var.set(dir_path)
            self.save_config()

    def load_config(self):
        import json
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "proj_dir" in data:
                        self.proj_dir_var.set(data["proj_dir"])
            except:
                pass

    def save_config(self):
        import json
        config_path = "config.json"
        data = {"proj_dir": self.proj_dir_var.get()}
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

    def set_progress(self, val):
        """Helper to update both progress bar and percentage label"""
        self.progress_bar.set(val)
        percent = int(val * 100)
        self.progress_label.configure(text=f"📊 TIẾN TRÌNH: {percent}%")

    def stop_rendering(self):
        self.cancel_requested = True
        self.log_textbox.after(0, self.update_progress, "[-] Yêu cầu DỪNG CHẠY! Đang đóng các tiến trình...")
        if hasattr(self, 'current_process') and self.current_process:
            try:
                import psutil
                parent = psutil.Process(self.current_process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except Exception:
                pass
        self.after(0, self.reset_ui)


    def select_video(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi")])
        if file_path:
            self.video_file = file_path
            if hasattr(self, 'auto_btn_video'):
                self.auto_btn_video.configure(fg_color="#555555")
            if hasattr(self, 'auto_lbl_video'):
                self.auto_lbl_video.configure(text=os.path.basename(file_path), text_color="#00e676")
            
            cap = cv2.VideoCapture(file_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if fps > 0: self.video_duration = frames / fps
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(150, frames-1))
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                self.raw_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.update_preview()
            else:
                messagebox.showerror("Lỗi", "Không thể đọc hình ảnh từ video!")

    def select_vi_srt(self):
        file_path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
        if file_path:
            self.vi_srt_file = file_path
            if hasattr(self, 'lbl_srt'):
                self.lbl_srt.configure(text=os.path.basename(file_path), text_color="#00e676")

    def select_logo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path:
            self.logo_file = file_path
            if hasattr(self, 'auto_btn_logo'):
                self.auto_btn_logo.configure(fg_color="#555555")
            if hasattr(self, 'auto_lbl_logo'):
                self.auto_lbl_logo.configure(text=os.path.basename(file_path), text_color="#00e676")
            self.logo_pos = None # Reset pos when new logo selected
            self.update_preview()

    def on_auto_src_change(self, value):
        if value == "File SRT có sẵn":
            self.chk_auto_trans.pack_forget()
            self.cb_auto_trans_model.pack_forget()
            self.entry_auto_context.pack_forget()
            self.btn_auto_select_srt.pack(side="left", padx=5)
            self.lbl_auto_srt_path.pack(side="left", padx=5)
            self.chk_auto_trans.pack(side="left", padx=10)
            self.cb_auto_trans_model.pack(side="left", padx=0)
            self.entry_auto_context.pack(side="left", padx=10)
        else:
            self.btn_auto_select_srt.pack_forget()
            self.lbl_auto_srt_path.pack_forget()

    def select_auto_srt(self):
        file_path = filedialog.askopenfilename(filetypes=[("SRT files", "*.srt")])
        if file_path:
            self.custom_auto_srt = file_path
            self.lbl_auto_srt_path.configure(text=os.path.basename(file_path))

    def on_style_change(self, *args):
        self.update_preview()

    def on_format_change(self, *args):
        # Lưu trạng thái của format TRƯỚC ĐÓ
        if hasattr(self, 'last_preview_fmt'):
            self.format_states[self.last_preview_fmt] = {
                "blur_boxes": list(self.blur_boxes),
                "logo_pos": self.logo_pos,
                "custom_sub_pos": getattr(self, 'custom_sub_pos', None),
                "font_size": self.font_size_var.get(),
                "font_color": self.font_color_var.get(),
                "logo_size": self.logo_size_var.get()
            }
        
        # Lấy format MỚI
        new_fmt = self.crop_format_var.get()
        self.last_preview_fmt = new_fmt
        
        state = self.format_states.get(new_fmt, None)
        if state is not None:
            self.blur_boxes = list(state.get("blur_boxes", []))
            self.logo_pos = state.get("logo_pos")
            self.custom_sub_pos = state.get("custom_sub_pos")
            if "font_size" in state: self.font_size_var.set(state["font_size"])
            if "font_color" in state: self.font_color_var.set(state["font_color"])
            if "logo_size" in state: self.logo_size_var.set(state["logo_size"])
        else:
            self.blur_boxes.clear()
            self.logo_pos = None
            self.custom_sub_pos = None
            
        self.update_preview()

    def on_canvas_resize(self, event):
        self.update_preview()

    def update_preview(self):
        if self.raw_frame is None: return
        
        # 1. Apply Crop
        frame = self.raw_frame.copy()
        h, w = frame.shape[:2]
        crop_fmt = self.crop_format_var.get()
        
        if "TikTok" in crop_fmt:
            new_w = int(h * 9 / 16)
            if new_w < w:
                start_x = (w - new_w) // 2
                frame = frame[:, start_x:start_x+new_w]
        elif "Vuông" in crop_fmt:
            new_size = min(w, h)
            start_x = (w - new_size) // 2
            start_y = (h - new_size) // 2
            frame = frame[start_y:start_y+new_size, start_x:start_x+new_size]
        elif "Youtube" in crop_fmt:
            new_h = int(w * 9 / 16)
            if new_h < h:
                start_y = (h - new_h) // 2
                frame = frame[start_y:start_y+new_h, :]

        # 2. Apply Mirror
        if self.chk_mirror_var.get():
            frame = cv2.flip(frame, 1)
        if self.chk_mirror_v_var.get():
            frame = cv2.flip(frame, 0)

        self.orig_h, self.orig_w = frame.shape[:2]

        # 3. Scale to Canvas
        self.canvas.delete("all")
        self.rects.clear()
        
        c_width = self.canvas_frame.winfo_width()
        c_height = self.canvas_frame.winfo_height()
        if c_width <= 1 or c_height <= 1:
            c_width, c_height = 800, 600
            
        self.scale = min(c_width / self.orig_w, c_height / self.orig_h)
        if self.scale > 1: self.scale = 1
        
        new_w, new_h = int(self.orig_w * self.scale), int(self.orig_h * self.scale)
        self.canvas.config(width=new_w, height=new_h)
        
        frame_resized = cv2.resize(frame, (new_w, new_h))
        self.image = Image.fromarray(frame_resized)
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        
        # 4. Redraw Blur Boxes
        for box in self.blur_boxes:
            bx, by, bw, bh = box
            x1 = int(bx * self.scale)
            y1 = int(by * self.scale)
            x2 = int((bx + bw) * self.scale)
            y2 = int((by + bh) * self.scale)
            r = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00e676", width=2)
            self.rects.append(r)

        # 5. Draw Logo
        self.logo_item = None
        if self.logo_file and os.path.exists(self.logo_file):
            try:
                img = Image.open(self.logo_file).convert("RGBA")
                size_mode = self.logo_size_var.get()
                if size_mode == "Nhỏ": img.thumbnail((80, 80))
                elif size_mode == "Vừa": img.thumbnail((150, 150))
                elif size_mode == "To": img.thumbnail((250, 250))
                
                lw, lh = img.size
                img = img.resize((max(1, int(lw * self.scale)), max(1, int(lh * self.scale))), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(img)
                
                # Setup default pos or saved pos
                if not self.logo_pos:
                    self.logo_pos = (20, 20)
                
                lx = int(self.logo_pos[0] * self.scale)
                ly = int(self.logo_pos[1] * self.scale)
                
                self.logo_item = self.canvas.create_image(lx, ly, image=self.logo_photo, anchor="nw", tags="logo")
                self.canvas.tag_bind("logo", "<ButtonPress-1>", self.on_logo_press)
                self.canvas.tag_bind("logo", "<B1-Motion>", self.on_logo_drag)
                self.canvas.tag_bind("logo", "<ButtonRelease-1>", self.on_logo_release)
                self.canvas.config(cursor="hand2")
            except Exception as e:
                print("Lỗi logo:", e)

        # 6. Draw Subtitle Preview (Vị trí phụ đề)
        # Tính toán tọa độ Y giống hệt cách FFmpeg render
        if hasattr(self, 'custom_sub_pos') and self.custom_sub_pos:
            sub_y_orig = self.custom_sub_pos[1]
        elif self.blur_boxes and self.orig_h > 0:
            lowest_box = max(self.blur_boxes, key=lambda b: b[1])
            bx, by, bw, bh = lowest_box
            # Phụ đề sẽ chèn vào tâm (theo chiều dọc) của Box thấp nhất
            sub_y_orig = by + (bh / 2.0)
        else:
            # Mặc định ở dưới cùng (cách đáy margin_v = 15 px của video gốc)
            # Theo FFmpeg ASS, marginV = 15 là cách đáy 1 chút
            sub_y_orig = self.orig_h - (self.orig_h * 15 / 288.0) # ước tính

        sub_y_canvas = int(sub_y_orig * self.scale)
        sub_x_canvas = int((self.orig_w / 2.0) * self.scale)

        font_size_val = int(self.font_size_var.get())
        canvas_font_size = max(14, int(font_size_val * 1.5 * self.scale))
        
        color_map = {"Vàng": "yellow", "Xanh lá": "#00FF00", "Đỏ": "red", "Trắng": "white"}
        tk_color = color_map.get(self.font_color_var.get(), "white")

        # Vẽ viền đen (Outline) cho chữ để dễ nhìn trên nền trắng/tuyết
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1), (0,-2), (0,2), (-2,0), (2,0)]:
            self.canvas.create_text(
                sub_x_canvas + dx, 
                sub_y_canvas + dy, 
                text="[Nắm kéo Vị trí Phụ đề Tiếng Việt]", 
                fill="black", 
                font=("Arial", canvas_font_size, "bold"), 
                justify="center", 
                anchor="center", 
                tags="subtitle_preview"
            )

        self.sub_item = self.canvas.create_text(
            sub_x_canvas, 
            sub_y_canvas, 
            text="[Nắm kéo Vị trí Phụ đề Tiếng Việt]", 
            fill=tk_color, 
            font=("Arial", canvas_font_size, "bold"), 
            justify="center", 
            anchor="center", 
            tags="subtitle_preview"
        )
        self.canvas.tag_bind("subtitle_preview", "<ButtonPress-1>", self.on_sub_press)
        self.canvas.tag_bind("subtitle_preview", "<B1-Motion>", self.on_sub_drag)
        self.canvas.tag_bind("subtitle_preview", "<ButtonRelease-1>", self.on_sub_release)

    # ====== XỬ LÝ KÉO THẢ LOGO & BOX ======
    def on_logo_press(self, event):
        self.dragging_logo = True
        self.drag_data = {"x": event.x, "y": event.y}
        
    def on_logo_drag(self, event):
        if self.dragging_logo:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.canvas.move(self.logo_item, dx, dy)
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            
    def on_logo_release(self, event):
        self.dragging_logo = False
        coords = self.canvas.coords(self.logo_item)
        if coords:
            self.logo_pos = (int(coords[0] / self.scale), int(coords[1] / self.scale))

    def on_sub_press(self, event):
        self.dragging_sub = True
        self.drag_sub_data = {"x": event.x, "y": event.y}
        
    def on_sub_drag(self, event):
        if hasattr(self, 'dragging_sub') and self.dragging_sub:
            # Chỉ cho phép kéo lên xuống (trục Y)
            dy = event.y - self.drag_sub_data["y"]
            self.canvas.move(self.sub_item, 0, dy)
            self.drag_sub_data["y"] = event.y
            
    def on_sub_release(self, event):
        self.dragging_sub = False
        coords = self.canvas.coords(self.sub_item)
        if coords:
            self.custom_sub_pos = (self.orig_w / 2.0, coords[1] / self.scale)

    def on_press(self, event):
        if getattr(self, 'dragging_logo', False) or getattr(self, 'dragging_sub', False): return
        items = self.canvas.find_withtag("current")
        if self.logo_item in items or getattr(self, 'sub_item', None) in items: return
            
        self.start_x, self.start_y = event.x, event.y
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#FF3366", width=2, dash=(4, 4))
        
    def on_drag(self, event):
        if self.dragging_logo: return
        if self.current_rect:
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)
        
    def on_release(self, event):
        if self.dragging_logo: return
        if self.current_rect:
            coords = self.canvas.coords(self.current_rect)
            if coords:
                x1, y1, x2, y2 = coords
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                
                rx1, ry1 = int(x1 / self.scale), int(y1 / self.scale)
                rx2, ry2 = int(x2 / self.scale), int(y2 / self.scale)
                
                rx1 = max(0, min(rx1, self.orig_w - 1))
                ry1 = max(0, min(ry1, self.orig_h - 1))
                rx2 = max(0, min(rx2, self.orig_w))
                ry2 = max(0, min(ry2, self.orig_h))
                
                rw, rh = rx2 - rx1, ry2 - ry1
                if rw > 2 and rh > 2:
                    if rw % 2 != 0: rw -= 1
                    if rh % 2 != 0: rh -= 1
                    self.blur_boxes.append((rx1, ry1, rw, rh))
                    self.canvas.itemconfig(self.current_rect, outline="#00e676", dash=())
                    self.rects.append(self.current_rect)
                else:
                    self.canvas.delete(self.current_rect)
            self.current_rect = None

    def undo_box(self, event=None):
        if self.blur_boxes and self.rects:
            self.blur_boxes.pop()
            r = self.rects.pop()
            self.canvas.delete(r)
            print("[*] Đã hoàn tác (Undo) vùng mờ.")


    def open_video_file(self):
        if self.output_video_path and os.path.exists(self.output_video_path):
            os.startfile(self.output_video_path)

    def lock_ui(self, msg):
        self.btn_translate.configure(state="disabled", text=msg)
        self.btn_preview.configure(state="disabled")

    def update_tts_progress(self, msg, pct=0.0):
        print(f"[*] {msg}")

    def get_color_code(self):
        c = self.font_color_var.get()
        if c == "Vàng": return "&H0000FFFF"
        if c == "Xanh lá": return "&H0000FF00"
        if c == "Đỏ": return "&H000000FF"
        return "&H00FFFFFF"

    def get_voice_code(self):
        c = self.voice_var.get()
        if "Nam Minh" in c: return "vi-VN-NamMinhNeural"
        return "vi-VN-HoaiMyNeural"

    def get_speed_code(self):
        c = self.speed_var.get()
        if c == "Bình thường": return "+0%"
        return c

    def get_color_code_ass(self, c):
        if c == "Vàng": return "&H0000FFFF"
        if c == "Xanh lá": return "&H0000FF00"
        if c == "Đỏ": return "&H000000FF"
        return "&H00FFFFFF"

    def create_ass_karaoke(self, srt_content, ass_path, font_size=20, font_color="&H00FFFFFF", bg_opacity=160, margin_v=25, res_x=1280, res_y=720):
        # ASS transparency: 0 is opaque, 255 is transparent. 
        # But của slider là 0 (transparent) to 255 (opaque). So we flip it.
        ass_alpha = 255 - bg_opacity
        alpha_hex = f"{ass_alpha:02X}"
        
        # Map màu nền sang BGR (ASS dùng định dạng &HAABBGGRR)
        bg_name = self.auto_sub_bg_color_var.get()
        bgr = "000000" # Mặc định Đen
        if bg_name == "Xanh dương": bgr = "FF0000"
        elif bg_name == "Đỏ": bgr = "0000FF"
        elif bg_name == "Xám": bgr = "A0A0A0"
        elif bg_name == "Vàng": bgr = "00FFFF"
        
        back_color = f"&H{alpha_hex}{bgr}"
        border_style = 3 if self.auto_chk_sub_bg_var.get() else 1
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{font_color},&H0000FFFF,{back_color},{back_color},-1,0,0,0,100,100,0,0,{border_style},2,0,2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        import pysrt
        try:
            subs = pysrt.from_string(srt_content)
            events = ""
            for sub in subs:
                start = sub.start.to_time().strftime("%H:%M:%S.%f")[:-4]
                end = sub.end.to_time().strftime("%H:%M:%S.%f")[:-4]
                text = sub.text.replace("\n", " ")
                words = text.split()
                if not words: continue
                
                total_cs = (sub.end.ordinal - sub.start.ordinal) // 10 
                if total_cs <= 0: total_cs = 10
                k_per_word = total_cs // len(words)
                
                kara_text = ""
                for word in words:
                    kara_text += f"{{\\k{k_per_word}}}{word} "
                
                events += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{kara_text.strip()}\n"
                
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(header + events)
            return True
        except Exception as e:
            print(f"[-] Lỗi tạo ASS Karaoke: {e}")
            return False

    def remove_vocal_advanced(self, video_path, output_dir):
        """Công nghệ tách giọng mới: Advanced Spectral Subtraction.
        Sử dụng xử lý tín hiệu số (DSP) để loại bỏ giọng nói mà không cần AI/PyTorch.
        """
        try:
            import librosa
            import soundfile as sf
            import numpy as np

            # 1. Trích xuất audio từ video
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            temp_input_wav = os.path.join(output_dir, "_temp_vocal_remove_in.wav")
            subprocess.run([
                ffmpeg_exe, "-y", "-nostdin", "-i", video_path,
                "-vn", "-ac", "2", "-ar", "44100", temp_input_wav
            ], capture_output=True, creationflags=CREATE_NO_WINDOW)

            if not os.path.exists(temp_input_wav): return ""

            # 2. Xử lý âm thanh (Công nghệ Vocal Reduction)
            print("[*] Đang lọc giọng (Đảm bảo giữ tiếng môi trường)...")
            y, sr = librosa.load(temp_input_wav, sr=None, mono=False)
            
            if y.ndim < 2 or y.shape[0] < 2:
                # Nếu là Mono: Giảm nhẹ dải tần giọng người (300-3000Hz)
                S = librosa.stft(librosa.to_mono(y))
                freqs = librosa.fft_frequencies(sr=sr)
                vocal_mask = (freqs > 300) & (freqs < 3000)
                S[vocal_mask, :] *= 0.5 # Giảm 50% giọng người
                y_final = librosa.istft(S)
            else:
                # Nếu là Stereo: Giảm Center Channel một cách cực kỳ nhẹ nhàng
                S_left = librosa.stft(y[0])
                S_right = librosa.stft(y[1])
                
                # Tính độ tương đồng
                mag_L, mag_R = np.abs(S_left), np.abs(S_right)
                similarity = np.minimum(mag_L, mag_R) / (np.maximum(mag_L, mag_R) + 1e-6)
                
                # GIỮ LẠI 80% ÂM THANH GỐC (Chỉ giảm 20% ở những nơi có giọng nói)
                # Điều này giúp tiếng môi trường gần như nguyên vẹn 100%
                mask = 1.0 - (similarity * 0.2) 
                
                # Áp dụng và chuyển về dạng sóng
                y_out_L = librosa.istft(S_left * mask)
                y_out_R = librosa.istft(S_right * mask)
                
                min_len = min(len(y_out_L), len(y_out_R))
                y_final = np.vstack([y_out_L[:min_len], y_out_R[:min_len]])


            # 3. Lưu kết quả
            output_wav = os.path.join(output_dir, "no_vocals_advanced.wav")
            # Soundfile cần (samples, channels)
            save_data = y_final.T if y_final.ndim > 1 else y_final
            sf.write(output_wav, save_data, sr)



            
            # Dọn dẹp file tạm
            if os.path.exists(temp_input_wav): os.remove(temp_input_wav)
            
            return output_wav

        except Exception as e:
            print(f"[-] Lỗi công nghệ tách giọng mới: {e}")
            return ""





    def run_video_burn(self, output_path, preview_mode=False, progress_offset=0.0, progress_scale=1.0, target_format=None, skip_tts=False):

        temp_srt = "_temp_subtitles.srt"
        temp_ass = "_temp_subtitles.ass"
        tts_audio = "_temp_tts_audio.wav"
        use_ass = self.auto_chk_karaoke_var.get()
        try:
            print("\n======================================")
            if not skip_tts:
                if self.chk_tts_var.get() and self.vi_srt_file and os.path.exists(self.vi_srt_file):
                    print("[*] Bắt đầu tạo giọng đọc AI & Đồng bộ Text...")
                v_code = self.get_voice_code()
                s_code = self.get_speed_code()
                
                preview_dur_sec = 0
                if preview_mode:
                    if hasattr(self, 'current_preview_dur'):
                        preview_dur_sec = self.current_preview_dur
                    else:
                        preview_dur_sec = 30
                        
                def tts_callback(msg, pct=0.0):
                    actual_pct = progress_offset + (pct * 0.3) * progress_scale
                    self.progress_bar.set(actual_pct)
                    self.log_textbox.after(0, self.update_progress, msg)
                        
                success = audio_maker.generate_tts_track(
                    self.vi_srt_file, int(self.video_duration * 1000), tts_audio, 
                    tts_callback, voice=v_code, speed=s_code, 
                    preview_duration=preview_dur_sec, output_srt_path=temp_srt
                )
                if not success: print("[-] Lỗi tạo TTS.")
            elif self.vi_srt_file and os.path.exists(self.vi_srt_file):
                shutil.copy2(self.vi_srt_file, temp_srt)
            
            if not os.path.exists(temp_srt) and self.vi_srt_file and os.path.exists(self.vi_srt_file):
                shutil.copy2(self.vi_srt_file, temp_srt)

            # --- BƯỚC TÁCH GIỌNG CÔNG NGHỆ MỚI (ADVANCED DSP) ---
            no_vocals_file = ""
            if self.auto_chk_vocal_remove_var.get():
                print("[*] Đang thực hiện tách giọng bằng công nghệ Advanced Spectral Subtraction...")
                work_dir = self.proj_dir_var.get()
                os.makedirs(work_dir, exist_ok=True)
                no_vocals_file = self.remove_vocal_advanced(self.video_file, work_dir)
                if no_vocals_file:
                    print(f"[+] Tách giọng thành công: {os.path.basename(no_vocals_file)}")
                else:
                    print("[-] Công nghệ tách giọng mới thất bại, dùng Phase Cancellation dự phòng.")



            print("[*] Đang nối Filter Graph và xuất Video...")
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            cmd = [ffmpeg_exe, "-nostdin", "-y", "-i", self.video_file]
            input_idx = 1

            # Thêm no_vocals.wav như input riêng nếu Demucs thành công
            no_vocals_idx = -1
            if no_vocals_file and os.path.exists(no_vocals_file):
                cmd.extend(["-i", no_vocals_file])
                no_vocals_idx = input_idx
                input_idx += 1
            
            logo_idx = -1
            if self.logo_file and os.path.exists(self.logo_file):
                cmd.extend(["-i", self.logo_file])
                logo_idx = input_idx
                input_idx += 1
                
            tts_idx = -1
            if self.chk_tts_var.get() and os.path.exists(tts_audio):
                cmd.extend(["-i", tts_audio])
                tts_idx = input_idx
                input_idx += 1

            filter_complex = ""
            v_out = "0:v"
            
            # --- 1. CẮT KHUNG HÌNH (CROP) LÀ BƯỚC ĐẦU TIÊN ---
            preview_fmt = self.crop_format_var.get()
            render_fmt = target_format or preview_fmt
            # Khôi phục toạ độ ĐÃ LƯU của định dạng đang render
            state = getattr(self, 'format_states', {}).get(render_fmt, None)
            
            # Default styles
            current_logo_size = self.logo_size_var.get()
            current_font_size = self.font_size_var.get()
            current_font_color = self.font_color_var.get()
            
            if state is not None:
                current_blur_boxes = list(state.get("blur_boxes", []))
                current_logo_pos = state.get("logo_pos")
                current_sub_pos = state.get("custom_sub_pos")
                current_logo_size = state.get("logo_size", current_logo_size)
                current_font_size = state.get("font_size", current_font_size)
                current_font_color = state.get("font_color", current_font_color)
                preview_fmt = render_fmt # Tọa độ chuẩn 1:1, không cần map chéo
            else:
                current_blur_boxes = list(self.blur_boxes)
                current_logo_pos = self.logo_pos
                current_sub_pos = getattr(self, 'custom_sub_pos', None)
            
            px, py = 0, 0
            pw, ph = self.vid_w, self.vid_h
            if "TikTok" in preview_fmt:
                pw = min(self.vid_w, int(self.vid_h * 9 / 16))
                px = (self.vid_w - pw) // 2
            elif "Vuông" in preview_fmt:
                pw = ph = min(self.vid_w, self.vid_h)
                px = (self.vid_w - pw) // 2
                py = (self.vid_h - ph) // 2
            elif "Youtube" in preview_fmt:
                ph = min(self.vid_h, int(self.vid_w * 9 / 16))
                py = (self.vid_h - ph) // 2
                
            rx, ry = 0, 0
            rw, rh = self.vid_w, self.vid_h
            if "TikTok" in render_fmt:
                rw = min(self.vid_w, int(self.vid_h * 9 / 16))
                rx = (self.vid_w - rw) // 2
            elif "Vuông" in render_fmt:
                rw = rh = min(self.vid_w, self.vid_h)
                rx = (self.vid_w - rw) // 2
                ry = (self.vid_h - rh) // 2
            elif "Youtube" in render_fmt:
                rh = min(self.vid_h, int(self.vid_w * 9 / 16))
                ry = (self.vid_h - rh) // 2
                
            crop_w, crop_h = rw, rh
            if crop_w != self.vid_w or crop_h != self.vid_h:
                filter_complex += f"[{v_out}]crop={crop_w}:{crop_h}:{rx}:{ry}[v_crop];"
                v_out = "v_crop"

            # --- 2. LẬT VIDEO ---
            flip_flags = []
            if self.chk_mirror_var.get():
                flip_flags.append("hflip")
            if self.chk_mirror_v_var.get():
                flip_flags.append("vflip")
            
            if flip_flags:
                filter_complex += f"[{v_out}]{','.join(flip_flags)}[v_flipped];"
                v_out = "v_flipped"
            
            # --- 3. LÀM MỜ ---
            if current_blur_boxes:
                for i, box in enumerate(current_blur_boxes):
                    bx, by, bw, bh = box
                    # Map box to render crop
                    abs_x = bx + px
                    abs_y = by + py
                    new_bx = int(abs_x - rx)
                    new_by = int(abs_y - ry)
                    
                    # Ensure within bounds
                    if new_bx < 0:
                        bw += new_bx
                        new_bx = 0
                    if new_by < 0:
                        bh += new_by
                        new_by = 0
                        
                    final_bw = min(int(bw), crop_w - new_bx)
                    final_bh = min(int(bh), crop_h - new_by)
                    final_bx = new_bx
                    final_by = new_by
                    
                    if final_bw <= 0 or final_bh <= 0: continue
                    
                    blur_radius = max(2, int(min(final_bw, final_bh) / 10))
                    if blur_radius > 15: blur_radius = 15
                    if blur_radius < 2: blur_radius = 2
                    
                    next_v_out = f"v_blurred_{i}"
                    filter_complex += f"[{v_out}]split=2[bg_{i}][fg_{i}];"
                    filter_complex += f"[fg_{i}]crop={final_bw}:{final_bh}:{final_bx}:{final_by},boxblur={blur_radius}:3[b_{i}];"
                    filter_complex += f"[bg_{i}][b_{i}]overlay={final_bx}:{final_by}[{next_v_out}];"
                    v_out = next_v_out
                
            # --- 4. CHÈN LOGO ---
            if logo_idx != -1:
                logo_size = current_logo_size
                size_filter = ""
                if logo_size == "Nhỏ": size_filter = "scale=80:-1,"
                elif logo_size == "Vừa": size_filter = "scale=150:-1,"
                elif logo_size == "To": size_filter = "scale=250:-1,"
                
                overlay_coord = "20:20" 
                if current_logo_pos:
                    abs_lx = current_logo_pos[0] + px
                    abs_ly = current_logo_pos[1] + py
                    new_lx = max(0, int(abs_lx - rx))
                    new_ly = max(0, int(abs_ly - ry))
                    overlay_coord = f"{new_lx}:{new_ly}"
                
                filter_complex += f"[{logo_idx}:v]{size_filter}format=rgba[logo_styled];[{v_out}][logo_styled]overlay={overlay_coord}[v_logo];"
                v_out = "v_logo"
                
            # --- 5. CHÈN PHỤ ĐỀ (CĂN CHUẨN) ---
            font_size = current_font_size
            c_name = current_font_color
            
            # Tính toán MarginV (Sử dụng đơn vị pixel trực tiếp vì PlayResY sẽ khớp với crop_h)
            # Ưu tiên tuyệt đối vị trí người dùng đã đặt (kéo thả)
            if current_sub_pos and ph > 0:
                sub_y_on_preview = current_sub_pos[1]
                margin_v = int(ph - sub_y_on_preview)
            else:
                # Nếu không kéo, mặc định nằm ở dưới (cách đáy 15/288 chiều cao)
                margin_v = int(ph * 15 / 288.0)
            
            if margin_v < 10: margin_v = 10
            if margin_v > ph - 50: margin_v = ph - 50

            # Điều chỉnh font size theo độ phân giải thực tế
            # Scale font từ chuẩn 288 lên độ cao thực tế của video
            ass_font_size = int(int(font_size) * ph / 288.0)
            if ass_font_size < 20: ass_font_size = 20


            if use_ass:
                with open(temp_srt, 'r', encoding='utf-8') as f:
                    srt_txt = f.read()
                
                ass_color = self.get_color_code_ass(c_name)
                opacity = self.auto_sub_opacity_var.get()
                if self.create_ass_karaoke(srt_txt, temp_ass, font_size=ass_font_size, font_color=ass_color, bg_opacity=opacity, margin_v=margin_v, res_x=crop_w, res_y=crop_h):
                    esc_ass = temp_ass.replace('\\', '/').replace(':', '\\:')
                    filter_complex += f"[{v_out}]subtitles='{esc_ass}'[v_sub];"
                    v_out = "v_sub"
            elif os.path.exists(temp_srt):
                if c_name == "Vàng": font_color = "&H0000FFFF"
                elif c_name == "Xanh lá": font_color = "&H0000FF00"
                elif c_name == "Đỏ": font_color = "&H000000FF"
                else: font_color = "&H00FFFFFF"
                
                # ÉP CHẾT Alignment=2 (Dưới - Giữa)
                style = f"FontSize={font_size},PrimaryColour={font_color},OutlineColour=&H00000000,BorderStyle=1,Outline=2,MarginV={margin_v},Alignment=2,Bold=1"
                esc_srt = temp_srt.replace('\\', '/').replace(':', '\\:')
                filter_complex += f"[{v_out}]subtitles='{esc_srt}':force_style='{style}'[v_sub];"
                v_out = "v_sub"


            # --- 6. XỬ LÝ ÂM THANH (Nâng cấp: Lọc giọng gốc + Ducking) ---
            bg_vol = self.bg_vol_var.get()
            a_out = ""
            
            is_mute = self.chk_mute_var.get()
            has_tts = (tts_idx != -1)

            if is_mute:
                # TRƯỜNG HỢP 1: TẮT TIẾNG GỐC
                if has_tts:
                    # Chỉ lấy giọng AI
                    filter_complex += f"[{tts_idx}:a]aformat=sample_rates=44100:channel_layouts=stereo[a_out_final];"
                    a_out = "a_out_final"
                else:
                    # Im lặng hoàn toàn
                    filter_complex += "anullsrc=r=44100:cl=stereo[a_mute];"
                    a_out = "a_mute"
            else:
                # TRƯỜNG HỢP 2: GIỮ TIẾNG GỐC (CÓ THỂ LỌC GIỌNG HOẶC DUCKING)
                # Chuẩn bị nhạc nền
                if no_vocals_idx != -1:
                    filter_complex += f"[{no_vocals_idx}:a]volume={bg_vol},aformat=sample_rates=44100:channel_layouts=stereo[v_bg_ready];"
                elif self.auto_chk_vocal_remove_var.get():
                    filter_complex += f"[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume={bg_vol},aformat=sample_rates=44100:channel_layouts=stereo[v_bg_ready];"
                else:
                    filter_complex += f"[0:a]volume={bg_vol},aformat=sample_rates=44100:channel_layouts=stereo[v_bg_ready];"

                if not has_tts:
                    # Giữ nguyên nhạc nền đã xử lý
                    a_out = "v_bg_ready"
                else:
                    # Trộn nhạc nền + Giọng AI (Ducking)
                    depth = self.duck_depth_var.get()
                    duck_ratio = 1 + (depth * 19)
                    duck_threshold = 0.15 - (depth * 0.14) 
                    filter_complex += f"[{tts_idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit[tts_side][tts_mix];"
                    # Chaining two compressors for super deep ducking (up to 400:1 ratio)
                    filter_complex += f"[v_bg_ready][tts_side]sidechaincompress=threshold={duck_threshold:.3f}:ratio={duck_ratio}:attack=10:release=400[a_duck_1];"
                    filter_complex += f"[a_duck_1][tts_side]sidechaincompress=threshold={duck_threshold:.3f}:ratio={duck_ratio}:attack=10:release=400[a_ducked];"
                    filter_complex += f"[a_ducked][tts_mix]amix=inputs=2:duration=first[a_out_final];"
                    a_out = "a_out_final"

            
            # --- KẾT THÚC FILTER COMPLEX ---
            filter_complex = filter_complex.rstrip(';')
            if filter_complex:
                cmd.extend(["-filter_complex", filter_complex])
            
            cmd.extend(["-map", f"[{v_out}]"])
            
            # Nếu a_out là một label từ filter_complex (không có dấu :) thì phải bọc []
            if ":" in a_out:
                cmd.extend(["-map", a_out])
            else:
                cmd.extend(["-map", f"[{a_out}]"])
                    
            if preview_mode:
                if hasattr(self, 'current_preview_dur'):
                    cmd.extend(["-t", str(self.current_preview_dur)])
                else:
                    cmd.extend(["-t", "30"])
                
            # FIX TRIỆT ĐỂ: Thêm các cờ tương thích cao nhất
            cmd.extend([
                "-c:v", "libx264", 
                "-preset", "ultrafast", 
                "-crf", "23", 
                "-pix_fmt", "yuv420p", 
                "-r", "30",
                "-map_metadata", "-1",        # Xóa sạch metadata cũ để tránh xung đột
                "-max_muxing_queue_size", "1024", 
                "-movflags", "+faststart", 
                "-c:a", "aac", 
                "-b:a", "192k", 
                "-ar", "44100", 
                "-y", 
                output_path
            ])
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                stdin=subprocess.DEVNULL,
                universal_newlines=True, 
                encoding='utf-8',
                creationflags=CREATE_NO_WINDOW
            )
            self.current_process = process
            
            error_log = []
            for line in process.stdout:
                if "time=" in line:
                    match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                    if match:
                        h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
                        curr_sec = h * 3600 + m * 60 + s
                        if self.video_duration > 0:
                            pct = min(curr_sec / self.video_duration, 1.0)
                            actual_pct = progress_offset + (0.3 + pct * 0.7) * progress_scale
                            self.set_progress(actual_pct)
                            self.log_textbox.after(0, self.update_progress, f"Đang Render Video: {int(pct*100)}% ({curr_sec:.1f}s / {self.video_duration:.1f}s)")
                else:
                    error_log.append(line.strip())
                    if len(error_log) > 15: error_log.pop(0)
                    
            process.wait()
            
            if process.returncode == 0:
                self.set_progress(1.0)
                if preview_mode:
                    print("\n[+] XONG PREVIEW 5s!")
                    os.startfile(output_path)
                else:
                    print("\n[+] RENDER THÀNH CÔNG!")
                    self.btn_open_video.pack(side="left", padx=5)
            else:
                print("\n[-] LỖI KHI RENDER!")
                print("\n".join(error_log))
        except Exception as e:
            print(f"\n[-] LỖI HỆ THỐNG: {e}")
        finally:
            self.after(0, self.reset_ui)
            
    def generate_auto_thumbnail(self, video_path, output_path):
        import subprocess
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        # Lấy frame ở giây thứ 5 làm ảnh bìa
        cmd = [ffmpeg_exe, "-y", "-i", video_path, "-ss", "00:00:05", "-vframes", "1", output_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)

    def update_progress(self, msg):
        lines = self.log_textbox.get("1.0", "end-1c").split("\n")
        if lines and "Đang Render" in lines[-1]:
            self.log_textbox.delete(f"{len(lines)}.0", "end")
            self.log_textbox.insert("end", "\n" + msg)
        else:
            self.log_textbox.insert("end", "\n" + msg)
        self.log_textbox.see("end")

    def open_proj_folder(self):
        folder = self.proj_dir_var.get()
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Cảnh báo", "Thư mục không tồn tại!")

    def save_settings(self):
        gemini = self.gemini_key_var.get().strip()
        openai_key = self.openai_key_var.get().strip()
        claude = self.claude_key_var.get().strip()
        
        env_content = f"GEMINI_API_KEY={gemini}\n"
        env_content += f"OPENAI_API_KEY={openai_key}\n"
        env_content += f"CLAUDE_API_KEY={claude}\n"
        
        try:
            with open(".env", "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # Reload env
            load_dotenv(override=True)
            
            messagebox.showinfo("Thành công", "Đã lưu API Keys thành công!")
            print("[+] Đã cập nhật file .env và nạp lại cấu hình.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file .env: {e}")

    def reset_ui(self):
        if hasattr(self, 'btn_auto_run'):
            self.btn_auto_run.configure(state="normal", text="🚀 CHẠY TOÀN BỘ")
        if hasattr(self, 'btn_stop_render'):
            self.btn_stop_render.configure(state="disabled")

    def lock_ui(self, msg):
        if hasattr(self, 'btn_auto_run'):
            self.btn_auto_run.configure(state="disabled", text=msg)
        if hasattr(self, 'btn_stop_render'):
            self.btn_stop_render.configure(state="normal")

    def start_auto_flow(self):
        if hasattr(self, 'btn_auto_open_folder'):
            self.btn_auto_open_folder.pack_forget()
        if not self.video_file:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn Video ở B2!")
            return
            
        base_proj_dir = self.proj_dir_var.get()
        if not base_proj_dir:
            base_proj_dir = os.path.join(os.path.expanduser("~"), "Videos", "LuanPro_Projects")
            
        os.makedirs(base_proj_dir, exist_ok=True)
        
        existing_dirs = [d for d in os.listdir(base_proj_dir) if os.path.isdir(os.path.join(base_proj_dir, d)) and d.startswith("VIDEO-")]
        next_num = 1
        if existing_dirs:
            nums = [int(d.split("-")[1]) for d in existing_dirs if d.split("-")[1].isdigit()]
            if nums:
                next_num = max(nums) + 1
                
        proj_name = f"VIDEO-{next_num:06d}"
        proj_path = os.path.join(base_proj_dir, proj_name)
        os.makedirs(proj_path, exist_ok=True)
        self.current_proj_dir = os.path.abspath(proj_path) # Chuẩn hóa đường dẫn tuyệt đối
        
        save_path = os.path.join(proj_path, f"{proj_name}_final.mp4")
        self.output_video_path = save_path
        
        self.btn_open_video.pack_forget()
        self.set_progress(0)
        self.cancel_requested = False
        
        self.lock_ui("⏳ ĐANG CHẠY AUTO...")
            
        threading.Thread(target=self._run_auto_pipeline, args=(save_path,), daemon=True).start()

    def _run_auto_pipeline(self, final_save_path):
        try:
            self.progress_bar.configure(mode="determinate")
            self.set_progress(0)
            base_dir = os.path.dirname(final_save_path)
            
            src_mode = self.auto_src_var.get()
            srt_path = os.path.join(base_dir, "temp_auto_extract.srt")
            
            # --- BƯỚC 1: LẤY SRT (0% -> 25%) ---
            self.log_textbox.after(0, self.update_progress, "\n[*] BƯỚC 1: ĐANG LẤY SRT TỪ VIDEO...")
            self.set_progress(0.05)
            
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            if src_mode == "File SRT có sẵn":
                if not hasattr(self, 'custom_auto_srt') or not self.custom_auto_srt:
                    self.log_textbox.after(0, self.update_progress, "[-] LỖI: Bạn chưa chọn file SRT để tải lên!")
                    self.after(0, self.reset_ui)
                    return
                import shutil
                shutil.copy2(self.custom_auto_srt, srt_path)
                self.log_textbox.after(0, self.update_progress, "[+] Đã nạp file SRT thủ công thành công.")
                self.set_progress(0.25)
            elif "Gemini API" in src_mode:
                # Dùng AI Gemini
                audio_temp = os.path.join(base_dir, "temp_auto_audio.mp3")
                cmd = [ffmpeg_exe, "-y", "-i", self.video_file, "-vn", "-c:a", "libmp3lame", "-q:a", "2", audio_temp]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                
                self.log_textbox.after(0, self.update_progress, "[*] Đang tải âm thanh lên máy chủ AI Gemini...")
                self.set_progress(0.1)
                
                import google.generativeai as genai
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    self.log_textbox.after(0, self.update_progress, "[-] Thiếu GEMINI_API_KEY trong .env!")
                    self.after(0, self.reset_ui)
                    return
                    
                genai.configure(api_key=api_key)
                
                try:
                    audio_file = genai.upload_file(path=audio_temp)
                except Exception as e:
                    self.log_textbox.after(0, self.update_progress, f"[-] Lỗi tải file âm thanh lên Gemini: {e}")
                    self.after(0, self.reset_ui)
                    return
                    
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                self.log_textbox.after(0, self.update_progress, "[*] AI đang nghe và chép chính tả (Speech-to-Text). Vui lòng đợi 1-2 phút...")
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
                
                prompt = "Please transcribe this audio and return ONLY a properly formatted SRT file. Do not include any markdown blocks, comments, or extra text."
                
                try:
                    response = model.generate_content([prompt, audio_file])
                except Exception as e:
                    self.log_textbox.after(0, self.update_progress, f"[-] Lỗi gọi API Nhận diện (Đã dừng tiến trình): {e}")
                    try: genai.delete_file(audio_file.name)
                    except: pass
                    self.after(0, self.reset_ui)
                    return
                
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.set_progress(0.25)
                
                srt_content = response.text.strip()
                if not srt_content:
                    self.log_textbox.after(0, self.update_progress, "[-] Lỗi: AI trả về kết quả rỗng!")
                    try: genai.delete_file(audio_file.name)
                    except: pass
                    self.after(0, self.reset_ui)
                    return
                    
                if srt_content.startswith("```"):
                    lines = srt_content.split('\n')
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].startswith("```"): lines = lines[:-1]
                    srt_content = '\n'.join(lines)
                    
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                
                try:
                    genai.delete_file(audio_file.name)
                    os.remove(audio_temp)
                except: pass
            elif "Phụ đề gốc" in src_mode:
                cmd = [ffmpeg_exe, "-y", "-i", self.video_file, "-map", "0:s:0?", srt_path]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                if not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0:
                    self.log_textbox.after(0, self.update_progress, "[-] LỖI: Video này KHÔNG có file phụ đề ẩn (Soft-sub)!")
                    self.log_textbox.after(0, self.update_progress, "=> Phụ đề tiếng Trung bạn thấy là Phụ đề CỨNG (Hard-sub) đã in chết vào video, không thể rút ra được.")
                    self.log_textbox.after(0, self.update_progress, "=> HƯỚNG DẪN: Hãy chọn 'Từ Âm Thanh (Whisper Offline)' ở B2 để máy nghe âm thanh và chép chính tả nhé!")
                    self.after(0, self.reset_ui)
                    return
                self.set_progress(0.25)
            elif "Whisper Offline" in src_mode:
                # Dùng Whisper (Chạy Offline)
                audio_temp = os.path.join(base_dir, "temp_auto_audio.mp3")
                cmd = [ffmpeg_exe, "-y", "-i", self.video_file, "-vn", "-c:a", "libmp3lame", "-q:a", "2", audio_temp]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                
                self.log_textbox.after(0, self.update_progress, "[*] Đang nạp mô hình Whisper (Lần đầu có thể mất vài phút tải Model)...")
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
                
                import shutil
                # Whisper bắt buộc phải gọi tên file chính xác là "ffmpeg.exe", nhưng imageio_ffmpeg có thể tên khác (vd: ffmpeg-win64.exe)
                temp_ffmpeg_dir = os.path.join(base_dir, "temp_ffmpeg_bin")
                os.makedirs(temp_ffmpeg_dir, exist_ok=True)
                temp_ffmpeg_exe = os.path.join(temp_ffmpeg_dir, "ffmpeg.exe")
                if not os.path.exists(temp_ffmpeg_exe):
                    shutil.copy2(ffmpeg_exe, temp_ffmpeg_exe)
                    
                if temp_ffmpeg_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = temp_ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
                    
                try:
                    from faster_whisper import WhisperModel
                    # Sử dụng CPU với compute_type int8 để tốc độ nhanh nhất
                    model = WhisperModel("base", device="cpu", compute_type="int8")
                except Exception as e:
                    self.log_textbox.after(0, self.update_progress, f"[-] Lỗi tải Faster-Whisper: {e}")
                    self.after(0, self.reset_ui)
                    return
                
                self.log_textbox.after(0, self.update_progress, "[*] Faster-Whisper đang xử lý âm thanh siêu tốc (Tiến trình đang chạy ngầm)...")
                
                try:
                    # beam_size=5 cho độ chính xác cao, word_timestamps=True để chia nhỏ sub
                    segments, info = model.transcribe(audio_temp, beam_size=5, word_timestamps=True)
                    
                    def format_timestamp(seconds):
                        hours = int(seconds // 3600)
                        minutes = int((seconds % 3600) // 60)
                        secs = int(seconds % 60)
                        millis = int((seconds - int(seconds)) * 1000)
                        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                        
                    srt_content = ""
                    idx = 1
                    for segment in segments:
                        words = list(segment.words) if segment.words else []
                        # Nếu câu quá dài (trên 10 từ), tự động chia nhỏ để dễ đọc
                        if len(words) > 10:
                            for j in range(0, len(words), 10):
                                chunk = words[j:j+10]
                                if not chunk: continue
                                start_t = format_timestamp(chunk[0].start)
                                end_t = format_timestamp(chunk[-1].end)
                                text_t = "".join([w.word for w in chunk]).strip()
                                srt_content += f"{idx}\n{start_t} --> {end_t}\n{text_t}\n\n"
                                idx += 1
                        else:
                            start_t = format_timestamp(segment.start)
                            end_t = format_timestamp(segment.end)
                            text_t = segment.text.strip()
                            srt_content += f"{idx}\n{start_t} --> {end_t}\n{text_t}\n\n"
                            idx += 1
                            
                    with open(srt_path, 'w', encoding='utf-8') as f:
                        f.write(srt_content.strip())
                        
                except Exception as e:
                    self.log_textbox.after(0, self.update_progress, f"[-] Lỗi chạy Whisper: {e}")
                    self.after(0, self.reset_ui)
                    return
                finally:
                    try: os.remove(audio_temp)
                    except: pass
                
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.set_progress(0.25)

            # --- BƯỚC 2: DỊCH SANG TIẾNG VIỆT (25% -> 50%) ---
            if self.auto_chk_extract_var.get():
                display_name = self.auto_trans_model_var.get()
                trans_model = self.model_mapping.get(display_name, "gemini-2.0-flash")
                self.log_textbox.after(0, self.update_progress, f"\n[*] BƯỚC 2: ĐANG DỊCH SRT BẰNG {display_name.upper()}...")
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
                
                with open(srt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                import translate
                translated_content = translate.translate_full_srt(content, model_name=trans_model, context=self.auto_context_var.get())
                
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.set_progress(0.5)
                
                if translated_content:
                    if translated_content.startswith("```"):
                        lines = translated_content.split('\n')
                        if lines[0].startswith("```"): lines = lines[1:]
                        if lines and lines[-1].startswith("```"): lines = lines[:-1]
                        translated_content = '\n'.join(lines)
                        
                    vi_srt_path = os.path.join(base_dir, "temp_auto_vi.srt")
                    with open(vi_srt_path, 'w', encoding='utf-8') as f:
                        f.write(translated_content)
                        
                    self.vi_srt_file = vi_srt_path
                    if hasattr(self, 'lbl_srt'):
                        self.lbl_srt.after(0, lambda: self.lbl_srt.configure(text=os.path.basename(vi_srt_path), text_color="#00e676"))
                    self.log_textbox.after(0, self.update_progress, "[+] Dịch thành công!")
                else:
                    self.log_textbox.after(0, self.update_progress, "[-] Lỗi dịch SRT. Hủy tiến trình.")
                    self.after(0, self.reset_ui)
                    return
            else:
                self.vi_srt_file = srt_path
                self.set_progress(0.5)

            # --- BƯỚC 3 & 4: RENDER VIDEO (CHE PHỤ ĐỀ, TẠO GIỌNG ĐỌC, GẮN PHỤ ĐỀ) (50% -> 100%) ---
            self.log_textbox.after(0, self.update_progress, "\n[*] BƯỚC 3: ĐANG RENDER VIDEO & TẠO GIỌNG ĐỌC AI...")
            
            is_preview = False
            if hasattr(self, 'auto_chk_preview_var') and self.auto_chk_preview_var.get():
                is_preview = True
                self.current_preview_dur = 60
                
            formats_to_run = []
            if getattr(self, 'auto_format_goc', None) and self.auto_format_goc.get(): formats_to_run.append("Giữ nguyên gốc")
            if getattr(self, 'auto_format_tiktok', None) and self.auto_format_tiktok.get(): formats_to_run.append("Dọc 9:16 (TikTok, Reels)")
            if getattr(self, 'auto_format_youtube', None) and self.auto_format_youtube.get(): formats_to_run.append("Ngang 16:9 (Youtube, Facebook)")
            if getattr(self, 'auto_format_vuong', None) and self.auto_format_vuong.get(): formats_to_run.append("Vuông 1:1 (Instagram)")
            
            if not formats_to_run:
                formats_to_run.append(self.crop_format_var.get())
                
            total_formats = len(formats_to_run)
            base_save = final_save_path.replace("_final.mp4", "")
            
            for i, fmt in enumerate(formats_to_run):
                self.log_textbox.after(0, self.update_progress, f"\n[*] Đang Render định dạng {i+1}/{total_formats}: {fmt}")
                if total_formats > 1:
                    fmt_suffix = "goc" if "Gốc" in fmt else "9_16" if "Dọc" in fmt else "16_9" if "Ngang" in fmt else "1_1"
                    current_save_path = f"{base_save}_{fmt_suffix}.mp4"
                else:
                    current_save_path = final_save_path
                    
                p_scale = 0.5 / total_formats
                p_offset = 0.5 + (i * p_scale)
                
                self.run_video_burn(current_save_path, preview_mode=is_preview, progress_offset=p_offset, progress_scale=p_scale, target_format=fmt, skip_tts=(i>0))
                
                # Tự động tạo ảnh bìa nếu chọn
                if not is_preview and self.auto_chk_thumbnail_var.get():
                    thumb_path = current_save_path.replace(".mp4", "_thumbnail.jpg")
                    self.generate_auto_thumbnail(current_save_path, thumb_path)
            
            self.log_textbox.after(0, self.update_progress, "\n[+] HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH AUTO!")
            if hasattr(self, 'btn_auto_open_folder'):
                self.btn_auto_open_folder.after(0, lambda: self.btn_auto_open_folder.pack(side="left", fill="x", expand=True, padx=(5, 0)))
            
        except Exception as e:
            self.log_textbox.after(0, self.update_progress, f"[-] [AUTO] Lỗi: {e}")
            if hasattr(self, 'btn_auto_open_folder'):
                self.btn_auto_open_folder.after(0, lambda: self.btn_auto_open_folder.pack(side="left", fill="x", expand=True, padx=(5, 0)))
            self.after(0, self.reset_ui)

if __name__ == "__main__":
    app = App()
    app.mainloop()

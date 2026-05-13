import os
import sys
import google.generativeai as genai
import openai
import anthropic
from dotenv import load_dotenv
import argparse
import time
import re
import json

# Load biến môi trường từ file .env
load_dotenv()

def translate_full_srt(content, model_name="gemini-2.0-flash", context=""):
    """
    Dịch file SRT một cách tối ưu token:
    1. Tách văn bản khỏi timestamp (Giảm ~50% input tokens).
    2. Chỉ gửi văn bản cần dịch lên Gemini.
    3. Sử dụng JSON format để nhận kết quả sạch, không rác (Giảm output tokens).
    4. Ghép lại timestamp sau khi dịch xong.
    """
    service = "Gemini"
    if model_name.startswith("gpt"): service = "OpenAI"
    elif model_name.startswith("claude"): service = "Claude"
    elif any(x in model_name for x in ["llama", "mixtral", "gemma", "distil"]): service = "Groq"
    
    api_keys = []
    service_prefix = service.upper()
    for k, v in os.environ.items():
        if k.startswith(f"{service_prefix}_API_KEY") and v.strip():
            api_keys.append(v.strip())
            
    if not api_keys:
        print(f"Lỗi: Không tìm thấy API KEY cho dịch vụ {service}. Vui lòng kiểm tra file .env.")
        return None

    # --- BƯỚC 1: PARSE SRT ĐỂ LẤY TEXT ---
    blocks = re.split(r'\n\s*\n', content.strip())
    srt_data = []
    texts_to_translate = []
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            idx = lines[0]
            timestamp = lines[1]
            text = " ".join(lines[2:]).strip()
            srt_data.append({"idx": idx, "timestamp": timestamp, "orig_text": text})
            texts_to_translate.append(text)
        elif len(lines) == 2 and "-->" in lines[1]: 
             srt_data.append({"idx": "", "timestamp": lines[0], "orig_text": lines[1]})
             texts_to_translate.append(lines[1])

    if not texts_to_translate:
        return content

    # --- BƯỚC 2: CHUẨN BỊ PROMPT ---
    system_prompt = (
        "Bạn là một chuyên gia dịch thuật phụ đề phim và video chuyên nghiệp. "
        "Dịch danh sách các đoạn văn bản sau sang tiếng Việt.\n\n"
        "YÊU CẦU QUAN TRỌNG:\n"
        "1. ĐÂY LÀ MỘT CÂU CHUYỆN LIÊN TỤC: Không dịch các dòng một cách rời rạc. Hãy đảm bảo sự liền mạch, giọng văn trôi chảy và tự nhiên như người bản xứ.\n"
        "2. NGỮ CẢNH VIDEO: Sử dụng từ ngữ phù hợp với ngữ cảnh video (ví dụ: vlog, phim, tài liệu). "
        "Nếu một câu bị ngắt giữa hai dòng phụ đề, hãy đảm bảo bản dịch của chúng khi ghép lại tạo thành một câu hoàn chỉnh về ngữ pháp và ý nghĩa.\n"
        "3. GIỮ NGUYÊN THỨ TỰ: Trả về một mảng JSON chứa các bản dịch theo đúng thứ tự của danh sách đầu vào.\n"
        "4. ĐỊNH DẠNG: Chỉ trả về mảng JSON ['bản dịch 1', 'bản dịch 2', ...], không thêm văn bản giải thích."
    )
    if context.strip():
        system_prompt += f"\n\nNGỮ CẢNH BỔ SUNG TỪ NGƯỜI DÙNG: {context.strip()}"

    # Đánh số để Gemini dễ theo dõi thứ tự, nhưng yêu cầu trả về mảng JSON
    user_prompt = "Dịch danh sách sau:\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts_to_translate)])

    # --- BƯỚC 3: GỌI API ---
    last_error = ""
    for i, api_key in enumerate(api_keys):
        for attempt in range(3):
            try:
                if service == "Gemini":
                    genai.configure(api_key=api_key)
                    # Sử dụng System Instruction để tối ưu token context
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_prompt
                    )
                    
                    # Cấu hình Response Schema để ép trả về JSON array
                    response = model.generate_content(
                        user_prompt,
                        generation_config={
                            "response_mime_type": "application/json",
                        }
                    )
                    
                    try:
                        translated_list = json.loads(response.text)
                        # Nếu Gemini trả về object { "translations": [...] }
                        if isinstance(translated_list, dict):
                            for key in ["translations", "data", "results"]:
                                if key in translated_list and isinstance(translated_list[key], list):
                                    translated_list = translated_list[key]
                                    break
                        
                        if not isinstance(translated_list, list):
                            # Nếu vẫn không phải list, thử tìm list bên trong
                            if isinstance(translated_list, dict):
                                for val in translated_list.values():
                                    if isinstance(val, list):
                                        translated_list = val
                                        break
                        
                        # Ghép lại SRT
                        final_srt = ""
                        for j, data in enumerate(srt_data):
                            # Lấy bản dịch nếu có, không thì giữ gốc
                            t_text = translated_list[j] if j < len(translated_list) else data['orig_text']
                            final_srt += f"{data['idx']}\n{data['timestamp']}\n{t_text}\n\n"
                        
                        print(f"[+] Đã dịch thành công bằng {model_name} (Sử dụng {len(response.text)} tokens output)")
                        return final_srt.strip()
                        
                    except Exception as je:
                        print(f"[-] Lỗi parse JSON: {je}. Nội dung nhận được: {response.text[:100]}...")
                        # Thử lại hoặc chuyển sang key khác
                        
                    # Giản lược logic OpenAI tương tự...
                    return response.choices[0].message.content
                
                elif service == "Groq":
                    import openai
                    client = openai.OpenAI(
                        api_key=api_key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"} if any(m in model_name for m in ["llama", "mixtral"]) else None
                    )
                    
                    try:
                        translated_list = json.loads(response.choices[0].message.content)
                        if isinstance(translated_list, dict):
                            for key in ["translations", "data", "results"]:
                                if key in translated_list and isinstance(translated_list[key], list):
                                    translated_list = translated_list[key]
                                    break
                        
                        if not isinstance(translated_list, list) and isinstance(translated_list, dict):
                            for val in translated_list.values():
                                if isinstance(val, list):
                                    translated_list = val
                                    break

                        final_srt = ""
                        for j, data in enumerate(srt_data):
                            t_text = translated_list[j] if j < len(translated_list) else data['orig_text']
                            final_srt += f"{data['idx']}\n{data['timestamp']}\n{t_text}\n\n"
                        
                        print(f"[+] Đã dịch thành công bằng Groq {model_name}")
                        return final_srt.strip()
                    except:
                        # Nếu lỗi JSON, thử lấy raw text
                        return response.choices[0].message.content
                
            except Exception as e:
                last_error = str(e)
                print(f"\n[!] Lỗi {service} (Key {i+1}, Lần {attempt+1}): {last_error}")
                if "429" in last_error or "quota" in last_error.lower(): break
                time.sleep(2)
                
    return None

def main():
    parser = argparse.ArgumentParser(description="Công cụ dịch file SRT tối ưu Token")
    parser.add_argument("input", help="Đường dẫn đến file SRT")
    parser.add_argument("-o", "--output", help="Đường dẫn đầu ra", default="")
    parser.add_argument("-m", "--model", help="Tên model", default="gemini-2.0-flash")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
         print(f"Lỗi: Không tìm thấy file {args.input}")
         sys.exit(1)
         
    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"[*] Đang dịch {args.input} (Tối ưu hóa Token)...")
    translated_content = translate_full_srt(content, args.model)
    
    if translated_content:
        output_file = args.output or args.input.replace(".srt", "_vi.srt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        print(f"[+] Đã lưu tại: {output_file}")
    else:
        print("[-] Dịch thất bại.")

if __name__ == "__main__":
    main()

import os
import sys
import google.generativeai as genai
import openai
import anthropic
from dotenv import load_dotenv
import argparse
import time

# Load biến môi trường từ file .env
load_dotenv()

def translate_full_srt(content, model_name="gemini-2.0-flash", context=""):
    """Dịch nguyên file SRT hỗ trợ Gemini, OpenAI, Claude"""
    service = "Gemini"
    if model_name.startswith("gpt"): service = "OpenAI"
    elif model_name.startswith("claude"): service = "Claude"
    elif "llama" in model_name.lower() or "mixtral" in model_name.lower(): service = "Groq"
    
    api_keys = []
    if service == "Gemini":
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY") and v.strip():
                api_keys.append(v.strip())
    elif service == "OpenAI":
        for k, v in os.environ.items():
            if k.startswith("OPENAI_API_KEY") and v.strip():
                api_keys.append(v.strip())
    elif service == "Claude":
        for k, v in os.environ.items():
            if k.startswith("CLAUDE_API_KEY") and v.strip():
                api_keys.append(v.strip())
    elif service == "Groq":
        for k, v in os.environ.items():
            if k.startswith("GROQ_API_KEY") and v.strip():
                api_keys.append(v.strip())
            
    if not api_keys:
        print(f"Lỗi: Không tìm thấy API KEY cho dịch vụ {service}. Vui lòng kiểm tra file .env.")
        return None
        
    prompt = """Bạn là một chuyên gia dịch thuật phụ đề phim.
Nhiệm vụ của bạn là dịch toàn bộ nội dung file SRT tiếng Trung dưới đây sang tiếng Việt.
YÊU CẦU BẮT BUỘC:
1. Giữ nguyên ĐÚNG cấu trúc file SRT: Số thứ tự -> Thời gian timestamp -> Nội dung đã dịch -> Dòng trống.
2. Dịch toàn bộ, KHÔNG bỏ sót câu nào.
3. CHỈ trả về văn bản SRT chuẩn, tuyệt đối KHÔNG chứa mã markdown (` ``` `) hay bất kỳ bình luận nào.
"""
    if context.strip():
        prompt += f"\nNGỮ CẢNH BỔ SUNG (Cực kỳ quan trọng để dịch sát nghĩa):\n{context.strip()}\n"

    prompt += "\nNội dung SRT gốc:\n"
    prompt += content
    
    last_error = ""
    for i, api_key in enumerate(api_keys):
        for attempt in range(3):
            try:
                if service == "Gemini":
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt, stream=True)
                    full_text = ""
                    for chunk in response:
                        if chunk.text:
                            full_text += chunk.text
                            print(chunk.text, end="", flush=True)
                    print("\n")
                    return full_text.strip()
                
                elif service == "OpenAI":
                    client = openai.OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        stream=True
                    )
                    full_text = ""
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            t = chunk.choices[0].delta.content
                            full_text += t
                            print(t, end="", flush=True)
                    print("\n")
                    return full_text.strip()
                
                elif service == "Claude":
                    # ... existing Claude logic ...
                    client = anthropic.Anthropic(api_key=api_key)
                    full_text = ""
                    with client.messages.stream(
                        model=model_name,
                        max_tokens=8192,
                        messages=[{"role": "user", "content": prompt}]
                    ) as stream:
                        for text in stream.text_stream:
                            full_text += text
                            print(text, end="", flush=True)
                    print("\n")
                    return full_text.strip()
                
                elif service == "Groq":
                    client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        stream=True
                    )
                    full_text = ""
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            t = chunk.choices[0].delta.content
                            full_text += t
                            print(t, end="", flush=True)
                    print("\n")
                    return full_text.strip()
                
            except Exception as e:
                last_error = str(e)
                print(f"\n[!] Lỗi dịch vụ {service} (Key {i+1}, Lần {attempt+1}): {last_error}")
                if "429" in last_error or "quota" in last_error.lower() or "limit" in last_error.lower():
                    break
                time.sleep(3)
                
        print(f"[-] Key thứ {i+1} của {service} thất bại. Đang chuyển sang Key tiếp theo...\n")
                
    print(f"\n[-] TẤT CẢ các API Key đều đã cạn kiệt! Lỗi cuối cùng: {last_error}")
    return None

def main():
    parser = argparse.ArgumentParser(description="Công cụ dịch file SRT tiếng Trung sang tiếng Việt bằng Gemini")
    parser.add_argument("input", help="Đường dẫn đến file SRT tiếng Trung")
    parser.add_argument("-o", "--output", help="Đường dẫn đến file SRT đầu ra (mặc định thêm '_vi' vào tên)", default="")
    parser.add_argument("-m", "--model", help="Tên model Gemini (mặc định: gemini-2.0-flash)", default="gemini-2.0-flash")
    args = parser.parse_args()
    
    input_file = args.input
    output_file = args.output
    
    if not output_file:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_vi{ext}"
        
    if not os.path.exists(input_file):
         print(f"Lỗi: Không tìm thấy file {input_file}")
         sys.exit(1)
         
    print(f"[*] Đang đọc file {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print(f"[*] Bắt đầu gửi ĐÚNG 1 REQUEST dịch nguyên file lên Gemini...")
    print(f"[*] Quá trình này có thể mất vài chục giây tùy độ dài file, vui lòng chờ...")
    translated_content = translate_full_srt(content, args.model)
    
    if translated_content:
        # Xoá markdown thừa nếu model không tuân thủ
        if translated_content.startswith("```"):
            lines = translated_content.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            translated_content = '\n'.join(lines)
            
        print(f"[*] Đang xuất kết quả ra file: {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        print("[+] Hoàn tất thành công!")
    else:
        print("[-] Dịch thất bại. Đã kết thúc tiến trình.")

if __name__ == "__main__":
    main()

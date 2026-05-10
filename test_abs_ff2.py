import os
import subprocess
import imageio_ffmpeg

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
abs_srt = os.path.abspath('test.srt')

# Try escaping colon with 4 backslashes
srt_escaped = abs_srt.replace('\\', '/')
srt_escaped = srt_escaped.replace(':', '\\\\\\\\:') 

filter_complex = f"[0:v]crop=100:100:10:10,boxblur=20:10[blurred];[0:v][blurred]overlay=10:10[with_blur];[with_blur]subtitles='{srt_escaped}':force_style='FontSize=22'"

cmd = [
    ffmpeg, '-y',
    '-f', 'lavfi',
    '-i', 'color=c=red:s=1280x720:d=5',
    '-filter_complex', filter_complex,
    '-c:v', 'libx264',
    'test_out.mp4'
]

print("Running command:", " ".join(cmd))
result = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", result.returncode)
print("STDERR:", result.stderr)

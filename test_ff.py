import os
import subprocess
import imageio_ffmpeg

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

srt_content = '''1
00:00:01,000 --> 00:00:02,000
Hello

'''
open('test.srt', 'w').write(srt_content)

filter_complex = "[0:v]crop=100:100:10:10,boxblur=20:10[blurred];[0:v][blurred]overlay=10:10[with_blur];[with_blur]subtitles='test.srt':force_style='FontSize=22'"

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
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)

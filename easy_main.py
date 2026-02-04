import whisper
import ffmpeg
import os

# 入力ファイル
input_file = "test_from_Satozaki_channel.mp4"

# 出力ファイル名を自動生成（例：test_cut.mp4）
base, ext = os.path.splitext(input_file)
output_file = f"{base}_cut{ext}"

# 1. Whisperで文字起こし
model = whisper.load_model("small")
result = model.transcribe(input_file)

# 2. 字幕用データ作成
segments = result['segments']

# 3. SRT生成
srt_file = f"{base}.srt"
with open(srt_file, "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        start = seg['start']
        end = seg['end']
        text = seg['text'].strip()
        # SRT形式に変換
        def to_srt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        f.write(f"{i}\n")
        f.write(f"{to_srt_time(start)} --> {to_srt_time(end)}\n")
        f.write(text + "\n\n")

# 4. ジェットカット用動画作成
# まず一時ファイルに分割してから結合する方法
clips = []
for i, seg in enumerate(segments):
    start = seg['start']
    end = seg['end']
    temp_file = f"clip_{i}.mp4"
    (
        ffmpeg
        .input(input_file, ss=start, t=(end-start))
        .output(temp_file, vcodec='libx264', acodec='aac', f='mp4', loglevel="error")
        .run()
    )
    clips.append(temp_file)

# 分割動画を結合
with open("concat.txt", "w") as f:
    for clip in clips:
        f.write(f"file '{clip}'\n")

ffmpeg.input("concat.txt", format="concat", safe=0).output(output_file, c="copy", loglevel="error").run()

# 一時ファイルを削除
for clip in clips:
    os.remove(clip)
os.remove("concat.txt")

print(f"生成完了: {output_file}")
print(f"字幕ファイル: {srt_file}")

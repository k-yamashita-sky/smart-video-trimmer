import whisper
import ffmpeg
import os
import re

# ========= 設定 =========
INPUT_FILE = "test_from_Satozaki_channel.mp4"
WHISPER_MODEL = "base"
PRE_BUFFER = 0.2     # 字幕の前に残す秒数
POST_BUFFER = 0.2    # 字幕の後に残す秒数
MAX_CHUNK_LENGTH = 30.0  # 秒単位で1つの一時ファイルの最大長
# ========================

base, ext = os.path.splitext(INPUT_FILE)
SRT_FILE = f"{base}.srt"
OUTPUT_FILE = f"{base}_cut{ext}"

# ---------- ① Whisperで文字起こし ----------
model = whisper.load_model(WHISPER_MODEL)
result = model.transcribe(INPUT_FILE)
segments = result["segments"]

if not segments:
    raise RuntimeError("文字起こし結果が空です")

# SRT書き出し
def to_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

with open(SRT_FILE, "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        f.write(f"{i}\n")
        f.write(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}\n")
        f.write(seg["text"].strip() + "\n\n")

print("① SRT生成 完了")

# ---------- ② SRT解析 & 区間作成 ----------
def srt_time_to_sec(t):
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

# 最初は字幕ごとの区間
intervals = []
for start, end in re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", open(SRT_FILE, encoding="utf-8").read()):
    s = max(0, srt_time_to_sec(start) - PRE_BUFFER)
    e = srt_time_to_sec(end) + POST_BUFFER
    intervals.append((s, e))

# 区間をまとめて MAX_CHUNK_LENGTH 以内に収める
merged_intervals = []
if intervals:
    cur_start, cur_end = intervals[0]
    for s, e in intervals[1:]:
        # つなげても最大長以内ならまとめる
        if s - cur_end <= 0.1 and (e - cur_start) <= MAX_CHUNK_LENGTH:
            cur_end = e
        else:
            merged_intervals.append((cur_start, cur_end))
            cur_start, cur_end = s, e
    merged_intervals.append((cur_start, cur_end))

print(f"一時クリップ数: {len(merged_intervals)}")

# ---------- ③ 一時ファイル作成 ----------
temp_files = []
for i, (s, e) in enumerate(merged_intervals):
    temp_file = f"temp_clip_{i}.mp4"
    (
        ffmpeg
        .input(INPUT_FILE, ss=s, t=e-s)
        .output(temp_file, vcodec="libx264", acodec="aac", loglevel="error")
        .run()
    )
    temp_files.append(temp_file)

# ---------- ④ concat用テキスト作成 ----------
concat_file = "concat_list.txt"
with open(concat_file, "w", encoding="utf-8") as f:
    for t in temp_files:
        f.write(f"file '{t}'\n")

# ---------- ⑤ 最終結合 ----------
ffmpeg.input(concat_file, format="concat", safe=0).output(
    OUTPUT_FILE, c="copy", loglevel="error"
).run()

# ---------- ⑥ 一時ファイル削除 ----------
for t in temp_files:
    os.remove(t)
os.remove(concat_file)

print("② 無音カット動画生成 完了")
print("\n=== 完了 ===")
print(f"動画: {OUTPUT_FILE}")
print(f"字幕: {SRT_FILE}")

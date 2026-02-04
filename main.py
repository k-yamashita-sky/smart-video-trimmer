import whisper
import ffmpeg
import os
import wave
import webrtcvad
import contextlib
import numpy as np

# ========================
# VADで音声区間を取得する関数
# ========================
def get_voice_segments(audio_path, aggressiveness=2, frame_duration=30):
    """
    webrtcvadを使って音声区間を検出
    aggressiveness: 0-3で厳しさ調整
    frame_duration: ms単位
    """
    vad = webrtcvad.Vad(aggressiveness)
    
    # WAVに変換して読み込み
    wav_path = "temp.wav"
    os.system(f'ffmpeg -y -i "{audio_path}" -ac 1 -ar 16000 "{wav_path}" >nul 2>&1')

    with contextlib.closing(wave.open(wav_path, 'rb')) as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        audio = wf.readframes(n_frames)

    # 16bit PCMを16bit整数に変換
    audio_int16 = np.frombuffer(audio, dtype=np.int16)
    
    frame_size = int(sample_rate * frame_duration / 1000)
    segments = []
    start = None
    for i in range(0, len(audio_int16), frame_size):
        frame = audio_int16[i:i+frame_size].tobytes()
        is_speech = vad.is_speech(frame, sample_rate)
        t = i / sample_rate
        if is_speech and start is None:
            start = t
        elif not is_speech and start is not None:
            end = t
            if end - start > 0.3:  # 0.3秒以上残す
                segments.append({'start': start, 'end': end})
            start = None
    # 最後の区間
    if start is not None:
        end = len(audio_int16)/sample_rate
        segments.append({'start': start, 'end': end})

    os.remove(wav_path)
    return segments

# ========================
# 字幕時間形式変換
# ========================
def to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

# ========================
# 入力ファイル
# ========================
input_file = "Ozaki_DeputyChiefCabinetSecretary_RegularPress_2026-02-04.mp4"
base, ext = os.path.splitext(input_file)
output_file = f"{base}_cut{ext}"
srt_file = f"{base}.srt"

# ========================
# 1. VADで音声区間を取得
# ========================
print("VADで音声区間を抽出中...")
vad_segments = get_voice_segments(input_file)

# ========================
# 2. Whisperで文字起こし
# ========================
print("Whisperで文字起こし中...")
model = whisper.load_model("base")  # medium/largeでも可
result = model.transcribe(input_file)

# WhisperのsegmentsをVADで抽出した範囲にフィルタリング
segments = []
for seg in result['segments']:
    for v in vad_segments:
        # 少し余裕を持たせる（前後0.2秒）
        start = max(seg['start'], v['start'] - 0.2)
        end = min(seg['end'], v['end'] + 0.2)
        if end - start > 0:
            segments.append({'start': start, 'end': end, 'text': seg['text']})

# ========================
# 3. SRT生成
# ========================
with open(srt_file, "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        f.write(f"{i}\n")
        f.write(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}\n")
        f.write(seg['text'].strip() + "\n\n")

# ========================
# 4. ジェットカット用動画作成
# ========================
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

# 🏭 PRODUCTION GUIDE — Quy trình sản xuất trọn bộ "Golden Hour"

> Toàn bộ lệnh chạy trong thư mục `echoes_plus_ep01/`. Máy cần: Python 3.10+, `pip install pillow numpy imageio-ffmpeg`.

## Sơ đồ pipeline

```
episode.json ──► fetch_photos_wikimedia.py ──► assets/photos/<slug>_{then,now}.jpg
       │                                             │
       └── TTS (giọng đã chọn, 10 clip/lượt) ──► assets/audio/*.mp3
                                                     │
                              build_audio.py  ──►  audio_master.wav + subtitles.srt
                                                     │
                              render_episode.py --render ──► output/GoldenHour_EP1.mp4
                                                     │
                              validate.py ──► kiểm tra duration/loudness/frames
```

## Bước 1 — Ảnh (chạy trên máy của bạn)

Sandbox này bị chặn mạng tới Wikimedia, nên `fetch_photos_wikimedia.py` được viết sẵn để bạn chạy ở nhà:

```bash
cd echoes_plus_ep01
python fetch_photos_wikimedia.py            # tải 50×2 ảnh CC/PD + ghi licenses.json
python fetch_photos_wikimedia.py --only 1-8 # chỉ pilot
```

Script tự: tìm ảnh theo `then_query`/`now_query` trong `episode.json`, lọc license CC/PD,
tải bản preview đủ lớn (≥800px), lưu metadata tác giả/license/URL vào `assets/photos/licenses.json`.
Ảnh đã tải bằng công cụ tìm kiếm cho 8 người pilot nằm sẵn ở `assets/pilot_photos/` (dùng làm fallback).

## Bước 2 — Giọng đọc & audio

1. Chọn giọng (audition). Mỗi lượt sinh tối đa 10 clip → full 50 người cần ~6 lượt.
2. `build_audio.py`:
   - Đo độ dài từng clip, dựng timeline: cold_open → card (3s) → act intro → mỗi sao = audio + 1.2s đệm; memory_break chèn ở ranh giới hồi.
   - Underscore: pad暖 tự sinh (hợp âm Am–F–C–G chậm, lowpass) duck −18 dB khi có lời, nổi 2s giữa các người.
   - Xuất `audio_master.wav` (48 kHz stereo) + `subtitles.srt` (chia cue theo câu, timing tỉ lệ số từ).

## Bước 3 — Render

```bash
python render_episode.py --render     # full; tự đọc timeline do build_audio.py xuất (timeline.json)
```

- 1280×720@30fps, Each star: THEN full-frame push 0–20% → wipe reveal 20–27% → split + caption tới hết.
- Tối ưu tốc độ: noise grain预 sinh 4 khung xoay vòng, vignette mask tính 1 lần, resize BILINEAR ở bước cuối.
- Ước lượng: ~0.08–0.15 s/frame → tập 32 phút chạy 1.5–3 giờ (nên chạy `--workers N` chia đoạn, có sẵn).

## Bước 4 — Xuất bản

- Mux audio: `ffmpeg -i video_silent.mp4 -i audio_master.wav -c:v copy -c:a aac -b:a 192k out.mp4`
- Loudness chuẩn: hai pass `loudnorm=I=-16:TP=-1.5:LRA=11`.
- Thumbnail: `make_packaging.py` (split THEN|NOW chữ "HE'S 100!" — xem `04_PACKAGING_EP01.md`).
- Kiểm tra checklist cuối trong `04_PACKAGING_EP01.md` mục 7 trước khi publish.

## TTS call budget (giới hạn 10 clip/lượt chat)

| Lượt | Nội dung | Số clip |
|---|---|---|
| 1 (pilot) | cold open + act1 intro + 8 story | 10 |
| 2 | sao 9–20 + card + break #1 | 13 → tách 10+3 |
| 3 | sao 21–30 + break #2 | 12 |
| 4 | sao 31–40 + break #3 | 12 |
| 5 | sao 41–50 + outro | 12 |

## Cấu trúc thư mục

```
echoes_plus_ep01/
├── 01_RESEARCH…  02_FORMAT…  03_SCRIPT…  04_PACKAGING…  05_PRODUCTION…  06_ASSETS…
├── episode.json               # 50 ngôi sao + verify facts + acts + breaks
├── fetch_photos_wikimedia.py  # B1 ảnh
├── build_audio.py             # B2 timeline + underscore + SRT
├── render_episode.py          # B3 renderer (+ --frames để xem thử)
├── validate.py                # B4 kiểm tra
└── assets/{photos,pilot_photos,audio,preview,thumbnails}
```

## An toàn nội dung (bắt buộc trước mỗi tập)
- Chạy lại cross-check "celebrity deaths 2026" (People / GoldDerby / Complex / Yahoo) — người nào vừa mất → chuyển sang mẫu tri ân hoặc loại.
- Kiểm tra từng mục `verify` trong `episode.json` bằng 1 lượt web search nhóm.
- Không AI hóa khuôn mặt; chỉ crop/light. Năm chụp hiển thị trên ảnh.

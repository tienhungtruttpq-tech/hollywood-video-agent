# gorilla_tech — agent tự động sản xuất video kiểu "Gorilla Tech"

> Pipeline tạo video kể chuyện công nghệ-quân sự giống video mẫu của kênh
> [Gorilla Tech](https://www.youtube.com/watch?v=8kfy2EBSkjM)
> (*"El Mi-28N ruso estaba a segundos de escapar… Ucrania LO HIZO ESTALLAR"*, 14:19):
> một vụ việc thật → kể như phim thriller nhưng kỷ luật tài liệu → bản đồ chiến thuật,
> thẻ thông số, đồng hồ đếm ngược, tỷ lệ chi phí → giọng đọc neural → phụ đề đốt sẵn →
> thumbnail + title/description/tags/chapters sẵn sàng đăng YouTube.

---

## 1. Nó làm gì (8 giai đoạn)

```
1 RESEARCH   Wikipedia + Wikimedia Commons (ảnh CC/PD)      → research/facts.json
2 SCRIPT     LLM viết narration + storyboard theo STYLE_GUIDE → script.json
             (fallback: template có sẵn / bộ viết deterministic, KHÔNG cần API key)
3 ASSETS     tải ảnh CC/PD khớp từng cảnh; AI-still chỉ khi bật GT_IMAGE_API_*
4 NARRATION  edge-tts (mặc định) / elevenlabs / openai / none → audio/*.mp3 + timing.json
5 SUBTITLES  word-boundaries → cues chuẩn broadcast         → output/*.srt + *.ass
6 SCORE      nhạc nền TỰ TỔNG HỢP (numpy), ducking sidechain → audio/mix.wav
7 RENDER     mỗi cảnh = 1 segment MP4 (Pillow+numpy → ffmpeg), concat, đốt ASS, mux
8 PACKAGE    thumbnail 1280×720, package.json (title/desc/tags/chapters), CREDITS.md
```

Mọi giai đoạn đều **cache theo nội dung** (`work/segments/*.hash`): sửa 1 cảnh → chỉ
vẽ lại cảnh đó. Không mạng? Tự chuyển offline: research đọc `cache/<topic>.json`,
script đọc `templates/<tên>.json`, TTS lùi về timing ước lượng.

## 2. Chạy nhanh

```bash
cd gorilla_tech
python -m pip install -r requirements.txt        # Pillow, numpy, edge-tts, imageio-ffmpeg

# A. Episode demo có sẵn trong repo (không cần mạng, không cần key):
python make_video.py --template mi28n-es --offline --tts none --minutes 12

# B. Episode mới, đủ giọng đọc + ảnh thật (cần mạng):
python make_video.py --topic "El Orlan-10 que vio demasiado" \
    --entities "STC Orlan-10,Wild Hornets" --lang es --minutes 10

# C. Smoke test 45 giây đầu ở 720p:
python make_video.py --template mi28n-es --tts edge --preview 45 --resolution 720p

# D. Chế độ agent tự hành (LLM quyết định từng bước):
python agent.py --topic "..." --lang es --minutes 10
python agent.py --test-api
```

Kết quả nằm ở `projects/<slug>/output/`: `<tên>.mp4`, `<tên>.srt`, `thumbnail.jpg`,
`package.json`, `description.txt`, `CREDITS.md`, `run_report.json`.

### Cờ hữu ích

| Cờ | Ý nghĩa |
|---|---|
| `--lang es\|en\|vi` | ngôn ngữ narration + mọi chữ trên màn hình |
| `--minutes N` | thời lượng đích (script tự cân đối số chữ ≈ N×150 từ) |
| `--resolution 720p\|1080p\|vertical` | profile khung hình |
| `--tts edge\|elevenlabs\|openai\|none` | engine giọng đọc |
| `--voice <tên>` | ghi đè voice, vd `es-ES-AlvaroNeural` |
| `--template <tên>` | dùng script mẫu trong `templates/` |
| `--script <file>` | dùng script.json tự viết |
| `--preview N` | chỉ render N giây đầu (QA nhanh) |
| `--no-music` / `--no-subs` / `--no-research` | tắt từng phần |
| `--workers N` | render song song N tiến trình |
| `--force` | bỏ cache, vẽ lại toàn bộ |
| `--stills` | xuất 1 ảnh JPG mỗi cảnh để duyệt mắt |

### Biến môi trường

| Biến | Mặc định | Dùng để |
|---|---|---|
| `GT_LLM_API_KEY` / `OPENAI_API_KEY` | key cũ của repo | cổng LLM OpenAI-compatible |
| `GT_LLM_API_BASE` / `GT_LLM_MODEL` | Experiential Labs / claude-fable-5.1 | đổi gateway/model |
| `GT_TTS_PROVIDER`, `GT_VOICE` | edge / voice đầu của ngôn ngữ | giọng đọc |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | — | TTS ElevenLabs |
| `GT_IMAGE_API_BASE/KEY/MODEL` | — | ảnh AI fallback (tắt = chỉ ảnh CC + đồ hoạ tự vẽ) |
| `GT_RESOLUTION`, `GT_FPS`, `GT_CRF`, `GT_WORKERS`, `GT_TARGET_MINUTES` | 1080p/30/22/4/13 | chất lượng & tốc độ |

## 3. Tự động hoá trên GitHub

Workflow `.github/workflows/miltech-video.yml`:

* **Chạy tay**: Actions → *miltech-video* → *Run workflow* (chọn topic / template /
  ngôn ngữ / thời lượng / độ phân giải / preview).
* **Chạy đêm**: cron `0 22 * * *` (05:00 giờ VN) — xoay vòng `topics.json` theo ngày.
* Mỗi run xuất **GitHub Artifact** (mp4 + srt + thumbnail + package.json + credits,
  giữ 30 ngày) và, với run đêm hoặc `release=true`, một **GitHub Release** vĩnh viễn.
* Secrets tuỳ chọn: `GT_LLM_API_KEY`, `ELEVENLABS_API_KEY`, `GT_IMAGE_API_*`.
  Không có secret nào thì vẫn chạy: script dùng template/fallback, giọng dùng edge-tts.

Muốn tắt chạy đêm: xoá khối `schedule:` trong workflow.

## 4. Công thức kênh mẫu (bắt buộc đọc trước khi sửa prompt)

`STYLE_GUIDE.md` — phân tích video mẫu thành beat-sheet + luật câu + ngữ pháp
on-screen + đóng gói YouTube. `prompts/script_system.txt` là bản nén của nó dùng
cho LLM. Nếu sửa một trong hai, giữ chúng khớp nhau.

## 5. Bản quyền & tuân thủ

* Ảnh: chỉ Wikimedia Commons với licence CC0/PD/CC-BY/CC-BY-SA; credit được đốt
  vào khung hình **và** ghi vào `output/CREDITS.md`.
* Nhạc: tổng hợp trong pipeline (`music.py`) — không dùng nhạc bên thứ ba.
* Nội dung chiến tranh: mô tả cơ khí, không hình ảnh thương vong, không cổ vũ.
* Số liệu lấy từ `research/facts.json`; LLM bị cấm bịa số (xem rule 1 của prompt).
  Các số của vụ Mi-28N đến từ episode tham chiếu / nguồn mở và được ghi chú là
  "khẳng định của nguồn" trong cache + template.

## 6. Cấu trúc thư mục

```
gorilla_tech/
├── make_video.py        orchestrator 8 giai đoạn (khuyên dùng)
├── agent.py + tools.py  chế độ agent tự hành (LLM loop + tools)
├── config.py util.py llm.py
├── research.py scripting.py assets.py voice.py subtitles.py
├── music.py render.py packaging.py
├── graphics.py visuals.py   ← toàn bộ ngôn ngữ hình ảnh (map/HUD/thẻ số…)
├── prompts/script_system.txt  STYLE_GUIDE.md
├── templates/mi28n-es.json    ← script mẫu đầy đủ (few-shot + demo offline)
├── cache/*.json               ← research offline cho demo
├── topics.json                ← hàng đợi episode cho cron
└── projects/                  ← output (được .gitignore)
```

## 7. English summary

`make_video.py` runs an 8-stage pipeline (research → LLM script → CC images →
neural TTS → broadcast subtitles → synthesised score → procedural tactical
graphics rendered per scene → YouTube packaging). Everything is cached and
offline-capable; the deterministic fallback writer and the bundled
`templates/mi28n-es.json` make the repo runnable with zero keys. The nightly
GitHub Action rotates `topics.json` and publishes each episode as an Artifact
and a Release. See `STYLE_GUIDE.md` for the narrative contract copied from the
reference channel.

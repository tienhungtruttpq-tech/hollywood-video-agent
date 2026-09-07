# 🌅 GOLDEN HOUR — Hollywood Then & Now (EP01)

**Trả lời cho yêu cầu:** nghiên cứu kênh đối thủ `@EchoesofHollywood-e4r` và xây dựng nội dung dài **hay hơn**.

## Deliverables
| File | Nội dung |
|---|---|
| `output/GoldenHour_Pilot.mp4` | **VIDEO PILOT 5:13** — cold open + Hồi I (8 sao đầu), giọng đọc, nhạc nền, 1280×720@30 |
| `output/subtitles.srt` | 42 cue phụ đề khớp lời đọc |
| `assets/thumbnails/thumb_A_100.jpg` | Thumbnail "HE'S 100!" (Dick Van Dyke 1961|2026) |
| `01_RESEARCH_ECHOES_OF_HOLLYWOOD.md` | Nghiên cứu đối thủ: 6 video gần nhất, view, công thức tiêu đề, 8 điểm yếu |
| `02_FORMAT_BLUEPRINT.md` | Blueprint format: 5 hồi, 3 nhịp kể chuyện, Memory Counter, visual/audio system |
| `03_SCRIPT_EP01_PILOT.md` | Kịch bản pilot có phân tích kỹ thuật |
| `episode.json` | **Kịch bản đầy đủ 50 sao** (~30 phút) + facts cần verify + góc ảnh cần tải |
| `04_PACKAGING_EP01.md` | 3 tiêu đề A/B, description + chapters, tags, lịch đăng, checklist publish |
| `05_PRODUCTION_GUIDE.md` | Pipeline chạy full tập 50 người trên máy bạn (TTS budget, render, loudness) |
| `fetch_photos_wikimedia.py` | Tải 50×2 ảnh CC/PD + licenses.json (chạy ở máy có mạng ra Wikimedia) |
| `build_audio.py` → `timeline.json` | Timeline + underscore tự sinh + ducking |
| `render_episode.py` / `render_pilot.py` | Renderer dùng chung / render pilot |
| `make_srt.py` | Sinh SRT từ timeline |
| `assets/pilot_photos/` | 16 ảnh thật đã crop của 8 sao pilot (kèm năm chụp) |

## Vì sao hay hơn đối thủ (tóm tắt)
1. Góc nội dung thắng nhất của họ ("còn sống đến 2026" — 69K views) nhưng có **cấu trúc 5 hồi** thay vì 33 phút phẳng.
2. **Memory Counter** biến người xem thành người chơi → comment → algorithm.
3. **Open loop đến người số 50** + callback Novak↔Hedren → giữ chân đến cuối.
4. **Outro tri ân** (Dolly Parton, Robert Duvall… đã mất 2026) — cảm xúc thay vì kết cụt.
5. **Fact-check bắt buộc**: `verify` từng người; black-list 2026 đã cross-check People/Complex/GoldDerby.
6. Ảnh thật có năm chụp, **không AI hóa mặt**; AI disclosure minh bạch như đối thủ.

## Chạy tiếp full tập (trên máy bạn)
```bash
cd echoes_plus_ep01
pip install pillow numpy imageio-ffmpeg imageio
python fetch_photos_wikimedia.py          # 100 ảnh cho 50 sao
# sinh TTS theo budget trong 05_PRODUCTION_GUIDE.md (5 lượt × 10 clip)
python build_audio.py --full
python render_pilot.py                    # hoặc renderer full trong guide
python make_srt.py
```

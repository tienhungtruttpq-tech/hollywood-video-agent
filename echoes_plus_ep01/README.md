# 🌅 GOLDEN HOUR — Hollywood Then & Now (EP01)

**Sản phẩm hoàn chỉnh: `output/GoldenHour_EP1_35Stars.mp4` — video 19,1 phút, 35 ngôi sao, giọng đọc + nhạc nền + phụ đề.**
Định dạng mô phỏng & nâng cấp từ kênh mẫu [@EchoesofHollywood-e4r](https://www.youtube.com/@EchoesofHollywood-e4r/videos) (nghiên cứu chi tiết: `01_RESEARCH_ECHOES_OF_HOLLYWOOD.md`).

## 📦 Deliverables

| File | Nội dung |
|---|---|
| **`output/GoldenHour_EP1_35Stars.mp4`** | 🎬 **VIDEO FULL EP1 — 19:07 phút** (1280×720, 30fps, 87.8 MB): cold open + 4 hồi + 35 sao + 2 memory break + outro |
| `output/subtitles.srt` | 188 phụ đề khớp lời đọc |
| `assets/thumbnails/thumb_A_100.jpg` | Thumbnail "HE'S 100!" |
| `assets/pilot_photos/` | 70 ảnh thật (35 sao × THEN/NOW) đã crop, có năm chụp |
| `01_RESEARCH_ECHOES_OF_HOLLYWOOD.md` | Nghiên cứu đối thủ: công thức tiêu đề, 8 điểm yếu, góc nội dung 69K views |
| `02_FORMAT_BLUEPRINT.md` | Blueprint format: 5 hồi, 3 nhịp kể chuyện, Memory Counter |
| `03_SCRIPT_EP01_PILOT.md` / `04_PACKAGING_EP01.md` / `05_PRODUCTION_GUIDE.md` | Kịch bản / Packaging / Guide mở rộng |
| `episode.json` | Dữ liệu 35 sao: narration, ảnh, cờ verify, spec bundle TTS |
| `build_audio.py` → `timeline.json` | Tách bundle TTS theo khoảng lặng (RMS snap), underscore Am–F–C–G, ducking |
| `render_episode.py` + `render_video.py` | Visual system (wipe reveal, act/break cards, grain) + renderer full |

## 🎬 Cấu trúc video (đã render)

```
00:00  COLD OPEN — hook "35 legends still with us in 2026" + teaser Meryl (#35)
00:39  ACT ONE  — Those We Never Forgot   (sao 1–8:  Van Dyke 100 → Novak 93)
01:33  ACT TWO  — The Faces in Our Living Room (sao 9–17: Shatner → Jaclyn Smith)
       ★ MEMORY BREAK #1 (17/35)
08:57  ACT THREE — The Soundtrack of Our Lives (sao 18–27: Willie → Nancy Sinatra)
       ★ MEMORY BREAK #2 (27/35) + "STILL SHARP" CTA
14:32  ACT FOUR — Still Turning Heads (sao 28–35: Nicholson → Meryl Streep)
17:45  OUTRO — tri ân Dolly Parton, Robert Duvall, Sam Neill… (mất 2026) + CTA
18:50  END CARD — "HOW MANY DID YOU REMEMBER?"
```
*(Timestamps chính xác nằm trong `timeline.json`; YouTube chapters copy từ đó.)*

## Vì sao hay hơn kênh mẫu
1. Góc nội dung thắng nhất của họ ("còn sống đến 2026" — 69K views) + **cấu trúc 4 hồi có cards** thay vì 33 phút phẳng.
2. **Memory Counter** trên màn hình + 2 MEMORY BREAK → biến xem thụ động thành trò chơi comment.
3. **Open loop** đến người cuối (Meryl) ngay từ cold open.
4. **Outro tri ân** cảm xúc (đối thủ kết cụt).
5. **Fact-safe**: đã loại người mất 2026; mỗi sao có `verify`; tuổi tính đúng ngày.
6. Ảnh thật, năm chụp hiển thị, **không AI hóa khuôn mặt**; narration AI được disclosure trong description (mẫu ở `04_PACKAGING`).

## Tái tạo / mở rộng
```bash
pip install pillow numpy imageio-ffmpeg imageio
python build_audio.py        # timeline + audio master (từ assets/audio/*.mp3)
python render_video.py       # render video (xong tự mux + loudnorm -16 LUFS)
python make_srt.py           # phụ đề (chỉnh lại mapping break nếu dùng episode khác)
```
Mở rộng lên 50 sao (EP2: các Dame/Knight Anh Quốc + 15 người dự trữ): xem `05_PRODUCTION_GUIDE.md`.

## ⚠️ Kiểm tra trước khi đăng
- Chạy lại cross-check "celebrity deaths 2026" — hiện tất cả 35 người ĐÃ XÁC MINH còn sống tính đến 06/09/2026.
- Ảnh nguồn: tìm kiếm web (mục đích giáo dục/tài liệu). Khi đăng thương mại, chạy `fetch_photos_wikimedia.py` để thay bằng ảnh CC/PD có license rõ.
```
EOF
cd /home/user/hollywood-video-agent && git add -A && git -c user.email="agent@arena.ai" -c user.name="Arena Agent" commit -q -m "EP1 full render: 35 stars, 19.1 min video with narration, music, SRT + cast photos + pipeline v2" && git log --oneline -3
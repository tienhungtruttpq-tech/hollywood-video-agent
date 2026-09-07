# 🎬 FORMAT BLUEPRINT — "Golden Hour: Hollywood Then & Now"

> Bản nâng cấp trực tiếp từ nghiên cứu `01_RESEARCH_ECHOES_OF_HOLLYWOOD.md`.
> Mục tiêu: **cùng góc nội dung thắng (69K views của đối thủ) nhưng giữ chân, tương tác và độ tin cậy cao hơn.**

---

## 1. Định vị

- **Tên chương trình:** Golden Hour — Hollywood Then & Now (không đụng brand "Echoes of Hollywood").
- **Tập dài:** 32–36 phút, **50 ngôi sao**, mỗi tập 1 chủ đề + góc "còn với chúng ta năm 2026 / bạn còn nhận ra không?".
- **Khán giả:** 45–75 tuổi, xem trên TV, trung thành, hay comment, nhạy với sự tôn trọng và CHÍNH XÁC.
- **Nguyên tắc số 1:** Ảnh thật — **không AI hóa khuôn mặt**. Năm chụp hiển thị ngay trên ảnh. Tuổi tính đúng theo ngày.

## 2. Cấu trúc 5 hồi (khác biệt lớn nhất so với đối thủ)

```
00:00 COLD OPEN (45–60s)  — hook ký ức + luật chơi Memory Counter + lời hứa kết
01:00 HỒI I   — Those We Never Forgot   (10 người)   → card hồi
07:30 HỒI II  — The Faces in Our Living Room (10 người) → card hồi + MEMORY BREAK #1
15:00 HỒI III — The Soundtrack of Our Lives (10 người) → card hồi + MEMORY BREAK #2
22:00 HỒI IV  — Still Turning Heads     (10 người)    → card hồi + MEMORY BREAK #3
28:30 HỒI V   — Across the Pond         (10 người)    → card hồi
34:00 OUTRO TRIBUTE (45–60s) — lời cảm ơn + tri ân những người vừa đi (VD: Dolly Parton, 8/2026)
                                + CTA comment "số điểm ký ức" + end screen
```

**Vì sao giữ chân tốt hơn:** người xem luôn biết "mình đang ở hồi nào"; card hồi tạo cảm giác tiến trình; 3 Memory Break chia nhịp tương tác; outro cho payoff cảm xúc (đối thủ kết cụt).

## 3. Mỗi người sao = 3 nhịp kể chuyện (biến thiên 25–45 giây)

| Nhịp | Nội dung | Ví dụ mẫu (Kim Novak) |
|---|---|---|
| **MEMORY** | 1 câu gọi ký ức cụ thể, có chi tiết hình ảnh | "Put her back in that grey suit at the foot of the stairs, and Vertigo comes rushing back…" |
| **TWIST** | Vượt ngoặt đời thật KHÁC vai diễn | "…but the woman who made mystery look beautiful walked away from it all — to paint, to write poetry, to live quietly in Oregon." |
| **NOW 2026** | Tuổi chính xác + 1 chi tiết hiện tại có kiểm chứng | "At 93, Venice stood to honor her — a Golden Lion for lifetime achievement, in 2025. She had returned on her own terms." |

**Quy tắc văn phong:**
- Câu ngắn–dài xen kẽ; mỗi 8–10 người đổi cách mở (không mở 50 lần bằng "X is easy to remember…").
- Người đã mất → giọng tri ân, không giật gân; nêu năm + tuổi.
- Mỗi hồi kết bằng "người mạnh nhất" của hồi đó (sắp xếp tăng dần độ sốc/cảm xúc).
- Callback giữa các người (Hitchcock → Tippi Hedren nhắc lại Vertigo của Novak ở Hồi I).

## 4. Memory Counter (vũ khí tương tác — đối thủ không có)

- Mở đầu: *"Keep count — how many of these faces do YOU still remember? Drop your number in the comments."*
- Overlay góc màn hình: `MEMORY COUNTER: 07` mờ dần sau mỗi tên.
- 3 thẻ MEMORY BREAK (5s) giữa các hồi: "Halfway there. How many so far? 🎬"
- Pinned comment mẫu + 3 community poll đồng bộ → phản hồi vòng lặp.

## 5. Visual system (1280×720 hoặc 1920×1080, 30fps)

1. **THEN → NOW reveal:** ảnh trẻ full màn + Ken Burns chậm (zoom 1.0→1.06) → vạch quét dọc 0.8s hé ảnh hiện tại → giữ split-screen 50/50 có đường phân cách.
2. **Caption chuẩn:** tên (serif đậm) + "b. 1933 · Now 93" + năm ảnh góc mỗi ảnh (`1933` / `2025`).
3. **Card hồi:** nền đen, gạch sáng vàng "golden hour", tên hồi serif — 2.5 giây.
4. **Film grain 3% + vignette nhẹ** — chất "chiếu phim cuối tuần", KHÔNG filter AI lên mặt.
5. **End screen 12s:** bóng ma các gương mặt đã qua + lời tri ân + thumbnail video kế.

## 6. Audio system

- **Narrator:** giọng ấm, trầm, chậm rãi kiểu tài liệu (TTS đã công khai trong description như đối thủ).
- **Underscore:** pad piano/dàn dây tự sản xuất (CC0), **đổi hợp âm/nhịp theo hồi**, duck −14 LU dưới lời thoại, nổi lên 2s giữa các người.
- Chuẩn loudness xuất bản: **−16 LUFS**, true peak ≤ −1.5 dB.

## 7. An toàn fact (bài học từ năm 2026 — năm nhiều ngôi sao lớn qua đời)

- **Danh sách đen 2026 (đã xác minh):** Dolly Parton (25/8/2026), Robert Duvall (15/2), Sam Neill, Chuck Norris, Tim Curry, Catherine O'Hara, James Van Der Beek, Bob Weir, Ted Turner, Bonnie Tyler, Neil Sedaka, Eric Dane, Ann Blyth (6/2026), Joanna Pettet, Louise Lasser… → **TUYỆT ĐỐI không đưa vào video "còn sống"**.
- Mỗi người trong `episode.json` có trường `verify: [...]` liệt kê mệnh đề phải kiểm tra trước khi publish.
- Tuổi tính theo ngày; người sinh trong mùa sinh chưa tới → dùng "turns 95 this month".
- Ảnh chỉ dùng nguồn tự do (Wikimedia Commons CC/PD) với năm chụp; script `fetch_photos_wikimedia.py` chạy trên máy người dùng (sandbox không truy cập được Wikimedia).

## 8. Packaging (chi tiết trong `04_PACKAGING_EP01.md`)

- Tiêu đề theo công thức đã decode của đối thủ + biến thể A/B (3 bản).
- Thumbnail: split THEN|NOW chính diện, chữ tối đa 4 từ, khuôn mặt ≥ 40% khung.
- Description: 2 đoạn cảm xúc + AI disclosure + **chapters đầy đủ từng hồi** (đối thủ không có).

## 9. Quy trình sản xuất (pipeline trong thư mục này)

```
episode.json (kịch bản 50 người, cờ verify)
   ├── fetch_photos_wikimedia.py  → tải ảnh CC/PD kèm license metadata (chạy trên máy bạn)
   ├── build_audio.py             → ghép TTS + underscore, xuất WAV master + SRT
   ├── render_episode.py          → dựng video (Ken Burns, wipe reveal, cards, grain)
   └── validate.py                → kiểm tra duration/loudness/frame cuối
```

TTS: các phân đoạn sinh bằng công cụ generate_speech (giọng đã audition `voice-…`), tối đa 10 clip/lượt → chia 5–6 lượt cho trọn tập 50 người.

# 📦 PACKAGING — Tập 1: "50 Legendary Stars Still With Us in 2026"

> Xây theo công thức đã decode từ đối thủ (xem `01_RESEARCH`) nhưng mạnh hơn: góc "còn sống 2026" (video 69K của đối thủ) + Memory Counter + chapters đầy đủ.

---

## 1. Tiêu đề — 3 biến thể A/B (YouTube A/B test native)

| Bản | Tiêu đề | Giả thuyết |
|---|---|---|
| **A (an toàn, mirror đối thủ)** | 50 Oldest Movie Stars Still With Us in 2026 — Can You Recognize Them Now? \| Then & Now 2026 | Copy góc thắng 69K của đối thủ |
| **B (thế hệ + cảm xúc)** | 50 Stars of the 60s–80s Who Are Still Alive in 2026 — Wait for #50 \| Then & Now 2026 | Hook "đợi đến số 50" tăng retention đến cuối |
| **C (drama tuổi tác)** | From 77 to 102: 50 Legendary Stars Still Shining in 2026 \| Then & Now 2026 | Con số 102 (Eva Marie Saint) là clickbait có thật |

**Khuyến nghị:** chạy A/B/C, chặn theo watch-time ở 30s & 8:00 (không chỉ CTR).

## 2. Thumbnail (kích thước 1280×720, an toàn TV)

- Bố cục: **split THEN | NOW** của Dick Van Dyke (100 tuổi) — bên trái 1961 nụ cười Bert, bên phải ảnh 2023+ gần nhất có được.
- Text: **"HE'S 100!"** góc phải trên (serif vàng khung đen) — max 4 từ.
- Khuôn mặt ≥ 40% khung hình; viền 8% trái/phải trống (YouTube overlay thời lượng).
- Không mũi tên đỏ, không vòng tròn đỏ — đối thủ không dùng, khán giả lớn tuổi ghét clickbait rẻ tiền.
- File: `assets/thumbnails/thumb_A_then_now.jpg` (tạo bằng `make_packaging.py`, KHÔNG dùng ảnh AI mặt người).

## 3. Description template

```
Fifty stars. Six decades. Every single one of them still with us in 2026. 🌟

From Dick Van Dyke at 100, to Eva Marie Saint at 102 — the oldest living
Oscar winner on Earth — revisit the faces that raised us, and see how they
look today. Keep count of how many YOU still remember, and drop your number
in the comments.

⏱ CHAPTERS
00:00 Welcome to Golden Hour
01:05 Act One — Those We Never Forgot (The Movie Stars)
00:00 #1 Dick Van Dyke (100)   ← điền timestamp thật sau khi render
...
34:00 In Memoriam — the legends we lost this year

▶ ABOUT THIS CHANNEL
Golden Hour — Hollywood Then & Now celebrates the stars of the 1950s–1990s
with respect, accuracy and original photographs. "NOW" means the latest
freely-licensed photograph we could verify; the year is always shown.

►DISCLOSURE
This video is produced in a documentary and educational format. The
narration voice is generated using AI technology for storytelling purposes.
Photographs are real and unaltered apart from cropping, stabilization and
lighting. No facts, identities, or events are intentionally altered.
Sources and image credits: [link to credits file]

#thenandnow #GoldenHourHollywood #celebrity #2026
```

Tags: `then and now 2026, oldest living actors, classic hollywood, golden age of hollywood, 60s 70s 80s stars, where are they now, celebrity news 2026, old hollywood, tributes, dick van dyke, clint eastwood, sophia loren, julie andrews, rita moreno, eva marie saint`

## 4. Community posts (đăng đồng bộ, học từ poll của đối thủ)

1. **Trước 1 ngày:** "50 stars of the 60s–80s are still with us in 2026. Guess: how many do you think YOU'll remember tomorrow at golden hour? 🎬" + poll (0–10 / 11–25 / 26–40 / all 50)
2. **Ngày đăng:** "Dick Van Dyke just turned 100. Eva Marie Saint is 102. Tonight they open our list of 50 legends still shining in 2026. Keep count — comment your number." + thumbnail teaser
3. **Sau 2 ngày:** poll 4 người như đối thủ: "Which of these Act One legends do you remember most vividly?" (Van Dyke / Novak / Loren / Andrews)

## 5. Pinned comment

> "Ready? Keep score as you watch — then tell me: 1️⃣ Your memory number (x/50) 2️⃣ The ONE face that unlocked the biggest memory. I read every comment at golden hour. ☀️"

## 6. Lịch xuất bản (học nhịp daily của đối thủ, bền hơn)

- Tập dài 1 tuần/1 (chất lượng > số lượng) + Shorts 3–5 cái/tập cắt từ 3 story hay nhất (Van Dyke 100, Saint 102, Novak Golden Lion).
- Playlist: "Still With Us — Then & Now 2026" + "Golden Hour Full Episodes".
- Ngày giờ: 17:00 thứ Sáu (khán giả 45–75, khung cuối tuần).

## 7. Checklist trước khi bấm Publish ⚠️

- [ ] Chạy lại cross-check deaths 2026 (People/GoldDerby/Complex) — loại ai vừa mất khỏi "còn sống"
- [ ] Kiểm tra từng `verify` field trong `episode.json`
- [ ] Ảnh có license + năm chụp đúng manifest
- [ ] SRT khớp narration, loudness −16 LUFS
- [ ] Chapters đúng timestamps render

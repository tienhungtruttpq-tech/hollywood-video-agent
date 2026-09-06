# Source-to-Original Video Agent

> Tạo project video **mới, có kiểm soát quyền sử dụng** từ một URL tham chiếu. Công cụ này được thiết kế để tránh luồng “tải về rồi đăng lại” và lưu bằng chứng/quy trình cần thiết trước khi xuất bản lên YouTube.

## Điều công cụ làm — và điều công cụ cố ý không làm

| Có | Không có |
| --- | --- |
| Kiểm tra URL công khai và đọc **metadata nhỏ** (tiêu đề/tác giả) | Tải/rip video, audio, captions, thumbnail hoặc stream của nguồn |
| Bắt buộc xác nhận cơ sở quyền sử dụng trước khi tạo project | Sao chép cảnh, thứ tự cảnh, phụ đề, lời thoại hoặc “đổi giọng/đổi màu” để đăng lại |
| Tạo brief, cấu trúc kịch bản mới, ledger quyền, checklist upload, báo cáo review | Hứa hẹn “qua Content ID”, “được bật kiếm tiền” hay đưa ra kết luận pháp lý |
| Render nhanh MP4 nháp từ typography + đồ họa procedural nguyên gốc | Tự động biến bất kỳ video của người khác thành video được phép đăng lại |

Một link bất kỳ có thể dùng làm **tham chiếu metadata**, nhưng bạn phải có quyền cần thiết và tự bổ sung giá trị gốc đáng kể. Đây là điểm quan trọng: YouTube đánh giá *reused content* tách biệt với copyright; ngay cả có permission, một bản chỉnh sửa tối thiểu vẫn có thể không đạt YPP. Mỗi project có `publish_checklist.md`; xem thêm các trang YouTube chính thức ở phần [Quy trình an toàn](#quy-trình-an-toàn).

## Cài đặt

Yêu cầu Python 3.10+ và FFmpeg được `imageio-ffmpeg` cung cấp tự động cho renderer.

```bash
cd /home/user/hollywood-video-agent
python -m pip install -r requirements.txt
```

Hoặc cài CLI vào môi trường đang dùng:

```bash
python -m pip install -e .
remake-agent --help
```

## Quy trình nhanh (Vietnamese)

### 1. Tạo project từ link video công khai

Chỉ chạy khi bạn thực sự sở hữu quyền hoặc có cơ sở quyền hợp lệ. Với video từ một channel, nên dùng link **video cụ thể**; với link channel/trang chung, luôn nhập `--topic` để brief có ý nghĩa.

```bash
python -m remake_agent remake \
  'https://www.youtube.com/watch?v=VIDEO_ID' \
  --rights owned \
  --confirm-rights \
  --topic 'Chủ đề tôi đã có quyền sản xuất' \
  --angle 'phân tích thực tế dựa trên nghiên cứu độc lập' \
  --language vi \
  --render
```

`--render` tạo ngay `output/original_draft.mp4`: video nháp im lặng, đồ họa procedural + chữ. Nó **không dùng bất kỳ media nào từ URL**. Mặc định chỉ 45 giây để preview nhanh; tăng bằng `--duration 90` khi cần.

Nếu dùng media được cấp phép, Creative Commons hoặc public domain, bằng chứng là bắt buộc (tài liệu không bị copy vào Git; chỉ tên/digest hoặc reference được lưu):

```bash
python -m remake_agent remake 'https://example.com/reference' \
  --rights permission --confirm-rights \
  --rights-evidence ~/private-rights/permission.pdf \
  --topic 'Một bài giải thích gốc' \
  --angle 'góc nhìn phản biện có trích dẫn'
```

Các giá trị `--rights`: `owned`, `licensed`, `permission`, `cc`, `public-domain`. Không có `--confirm-rights`, hoặc thiếu evidence khi cần, lệnh bị chặn trước khi tạo project.

### 2. Viết/ghi âm phần đóng góp nguyên gốc

Mở project mới trong `projects/<ten>-<timestamp>/`:

- `script.md` là **khung kịch bản mới**, không phải transcript/translation/paraphrase của video tham chiếu. Thay toàn bộ prompt trong ngoặc bằng nghiên cứu và bình luận của bạn.
- Tự ghi voice-over/on-camera commentary gốc hoặc dùng giọng có giấy phép thương mại. Không bắt chước giọng người thật.
- Chỉ thêm visual, footage, nhạc, font, voice hoặc asset AI mà bạn có quyền dùng. Ghi tất cả vào `rights_ledger.csv`.
- Giữ hợp đồng/email/giấy phép gốc ngoài repository riêng tư; công cụ chỉ lưu digest/reference của evidence.

### 3. Review trước khi upload

Điền tất cả cột trong `rights_ledger.csv`, sau đó chạy từ repository (thay đường dẫn bên dưới):

```bash
python -m remake_agent review \
  --project projects/ten-project-YYYYMMDD-HHMMSS \
  --has-original-voiceover \
  --assets-ledger-complete
```

Lệnh tạo/cập nhật `compliance_report.json`. Mã thoát `0` chỉ nghĩa là các **khai báo workflow** đã đủ; vẫn bắt buộc rà soát người thật về quyền, facts, Community Guidelines và luật địa phương.

Nếu video có AI chân thực/mang tính thay đổi đáng kể (người/sự kiện/địa điểm/giọng nói/nhạc), thêm `--realistic-ai`. Báo cáo sẽ không cho trạng thái `publish_ready`; bạn cần bật disclosure **Altered or synthetic content** trong YouTube Studio rồi hoàn tất human review.

### Render lại nháp

```bash
python -m remake_agent render \
  --project projects/ten-project-YYYYMMDD-HHMMSS \
  --duration 45 --resolution 1280x720 --fps 24
```

Renderer chỉ tạo visual abstract, không truy cập URL lúc render và không tự mux audio. Nhờ đó nháp nhanh vẫn không vô tình dùng nội dung của nguồn. Bản MP4 nháp mang nhãn yêu cầu thêm voice-over gốc và kiểm tra quyền; không phải bản sẵn sàng upload.

## Quy trình an toàn

1. **Khẳng định quyền có thể chứng minh.** Ghi credit, “no copyright intended”, mục đích giáo dục, hoặc dùng vài giây media không tự tạo quyền.
2. **Không dùng source như raw footage.** Agent không download/transcribe URL; đừng thêm source clip/audio/caption/thumbnail qua đường vòng vào project.
3. **Làm video đứng độc lập.** Thêm luận điểm, nghiên cứu, diễn giải, giọng nói/hình ảnh hoặc giá trị giáo dục–giải trí mới thật sự; không tạo nhiều bản template lặp lại hàng loạt.
4. **Theo dõi asset.** `rights_ledger.csv` có quyền, điều khoản, attribution và vị trí dùng của từng asset.
5. **Minh bạch AI.** Khi YouTube yêu cầu disclosure cho nội dung realistic/meaningfully synthetic, hãy khai báo trong Studio.
6. **Con người quyết định xuất bản.** Không tool nào có thể tự xác định fair use, tính hợp lệ của giấy phép, Community Guidelines, Content ID hay YPP eligibility.

Các tài liệu YouTube nên xem trước mỗi đợt phát hành:

- [YouTube channel monetization policies (reused/inauthentic content)](https://support.google.com/youtube/answer/1311392)
- [Common copyright myths](https://support.google.com/youtube/answer/2797449)
- [Disclosing altered or synthetic content](https://support.google.com/youtube/answer/14328491)

## Bảo mật cấu hình cũ

Pipeline `agent.py` cũ (Then & Now) hiện đọc key từ biến môi trường `EXPERIENTIAL_LABS_API_KEY`; repository không chứa key mới. Ví dụ:

```bash
export EXPERIENTIAL_LABS_API_KEY='...'
python agent.py --topic 'Hollywood Actors Then and Now'
```

## Kiểm thử

```bash
python -m unittest discover -s tests -v
```

## Git hygiene

`projects/` và video output được ignore để không đưa file render/bằng chứng quyền riêng tư lên GitHub. Code, tests và tài liệu workflow là những phần cần commit để tái sử dụng.

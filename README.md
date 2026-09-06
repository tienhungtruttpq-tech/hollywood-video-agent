# hollywood-video-agent

Kho chứa hai agent sản xuất video tự động:

| Thư mục | Agent | Đầu ra |
|---|---|---|
| `gorilla_tech/` | **MilTech storytelling agent** — video kể chuyện công nghệ-quân sự theo format kênh [Gorilla Tech](https://www.youtube.com/watch?v=8kfy2EBSkjM): research → kịch bản LLM → bản đồ chiến thuật/thẻ thông số tự vẽ → giọng đọc neural → phụ đề → nhạc tự tổng hợp → thumbnail + metadata YouTube. Chạy đêm trên GitHub Actions. | `gorilla_tech/projects/<slug>/output/*.mp4` |
| `hollywood_full/`, `hollywood_actresses/`, `new_project/` | **Hollywood Then & Now agent** — video so sánh diễn viên "then vs now" từ ảnh Wikimedia CC, có agent loop (`agent.py` + `tools.py` ở gốc repo). | `*/output/*.mp4` |

## Bắt đầu nhanh (agent mới)

```bash
cd gorilla_tech
python -m pip install -r requirements.txt
python make_video.py --template mi28n-es --offline --tts none   # demo không cần mạng/key
python make_video.py --topic "..." --lang es --minutes 10       # episode mới (cần mạng)
```

Chi tiết đầy đủ: [`gorilla_tech/README.md`](gorilla_tech/README.md) ·
công thức kể chuyện của kênh mẫu: [`gorilla_tech/STYLE_GUIDE.md`](gorilla_tech/STYLE_GUIDE.md) ·
tự động hoá: [`.github/workflows/miltech-video.yml`](.github/workflows/miltech-video.yml).

## Trạng thái

* Nhánh làm việc: `arena/01a07733-hollywood-video-agent`
* CI: workflow `miltech-video` (workflow_dispatch + cron 22:00 UTC) xuất Artifact/Release.
* Mọi file lớn (mp4, ảnh tải về, workspace render) đều nằm ngoài Git qua `.gitignore`.

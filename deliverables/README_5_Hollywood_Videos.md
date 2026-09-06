# Five Hollywood Then & Now Videos

Five finished 8-minute English-language, 1280×720 videos created from this repository's Then & Now format.

## Delivered MP4s
- `01_Hollywood_Leading_Men_Then_Now.mp4` — Hollywood Leading Men
- `02_Hollywood_Leading_Ladies_Then_Now.mp4` — Hollywood Leading Ladies
- `03_Action_Movie_Icons_Then_Now.mp4` — Action Movie Icons
- `04_Nineties_Hollywood_Icons_Then_Now.mp4` — Nineties Hollywood Icons
- `05_Hollywood_Comedy_Stars_Then_Now.mp4` — Hollywood Comedy Stars

Every MP4 contains an embedded English subtitle track; matching `.srt` files are included for upload platforms. The collection uses a user-approved English narration voice and an original procedural ambient score.

## Re-render

```bash
.venv/bin/python batch5/create_manifest.py
.venv/bin/python batch5/import_assets.py
.venv/bin/python batch5/render_batch.py --all
```

See `Hollywood_Then_Now_5_Videos_Credits.md` for source/attribution records and `Batch_5_Validation.json` for the encoded-file checks.

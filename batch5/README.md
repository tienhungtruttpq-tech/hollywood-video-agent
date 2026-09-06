# Hollywood Then & Now — five-video batch

This production workspace creates five English-language Hollywood `Then & Now` episodes from the repository's existing format and research records.

## Finished deliverables

The generated, self-contained files are in `batch5/output/`:

1. `01_Hollywood_Leading_Men_Then_Now.mp4`
2. `02_Hollywood_Leading_Ladies_Then_Now.mp4`
3. `03_Action_Movie_Icons_Then_Now.mp4`
4. `04_Nineties_Hollywood_Icons_Then_Now.mp4`
5. `05_Hollywood_Comedy_Stars_Then_Now.mp4`

Each master is 1280×720, 24 fps and exactly 8:00 long. It includes AAC audio and an embedded English `mov_text` subtitle track. Sidecar `.srt` files, title-frame thumbnails, credits, and `Batch_5_Validation.json` are alongside the masters.

## Creative and sourcing approach

- Six performers appear in each episode with a portrait pair, career card, original English narration and low-key, locally generated ambient score.
- The first four episode manifests inherit the researched photo records in `hollywood_full/actors.json` and `hollywood_actresses/actors.json`.
- The comedy episode's Commons authors and licenses were checked against the Commons API and written into `episodes.json` / the generated credits.
- Portrait assets are edited only for framing, colour treatment, layout and motion. No AI face replacement or fabricated celebrity footage is used.

## Re-rendering

Create a local virtual environment and install the compact render stack:

```bash
python -m venv .venv
.venv/bin/python -m pip install Pillow numpy imageio-ffmpeg
.venv/bin/python batch5/create_manifest.py
.venv/bin/python batch5/import_assets.py
.venv/bin/python batch5/render_batch.py --all
```

`--preview` renders a 24-second review excerpt for a chosen episode, for example:

```bash
.venv/bin/python batch5/render_batch.py --episode 01_leading_men --preview
```

Use `--package` only when a duplicated ZIP copy of all rendered MP4s is actually needed. Large production assets, scene intermediates and finished binaries are intentionally ignored by Git.

# Hollywood THEN & NOW — eight-minute edition V2

## Deliverables

- `output/Hollywood_Then_Now_8min_V2.mp4` — the finished 480-second, 1280×720, 30 fps video.
- `output/Hollywood_Then_Now_8min_EN.srt` — full English narration subtitles.
- `output/Hollywood_Credits_8min.md` — all 60 photo records, music credit and reuse terms.
- `output/Nang_cap_V2.md` — Vietnamese explanation of the researched effects and changes from the approved demo.
- `output/Hollywood_Narration.txt` — clean English narration text.
- `output/Hollywood_8min_Poster.jpg` — a title-frame image.

The spoken introduction and ending are captioned, as are all 30 comparisons. The visual edit uses real dated source photographs, not AI aging or face generation. “NOW” means the later photograph, with its year shown explicitly.

## Persisted production material

- `actors.json`: chosen photographs, creator/license/source metadata and dates.
- `framing.json`: reviewed crop rectangles, retained so automatic suggestions are not silently substituted on later renders.
- `narrative.json`: eight narration batches and 32 timeline sections.
- `timing.json`: final speech placements, sentence-caption times and reveal times.
- `assets/photos/`: the source-matched working images.
- `assets/Dream_Culture_Kevin_MacLeod.mp3`: licensed instrumental score.
- `assets/fonts/`: fonts and their OFL notices.
- `audio/Narration_English.flac`: the full, lossless, music-free English narration master.
- `work/validation_v2.json`: technical checks recorded after final encoding.

Large raw speech batches, prepared portrait tiles, temporary PCM mixes, ASR models and intermediate video parts live under `/home/user/.cache/hollywood_full/`. They are disposable and are not required to retain the finished video.

## Recreate the edit without generating speech again

```bash
cd /home/user/hollywood_full
python -m pip install -r requirements.txt
python prepare_photos.py
python mix_audio_v2.py
python render_v2.py --preview
python render_v2.py --render --workers 2
python validate_v2.py
```

`mix_audio_v2.py` reads the persisted FLAC narration and reconstructs the music mix. The FFmpeg executable is supplied by `imageio-ffmpeg`; a system FFmpeg installation is not required.

`align_audio.py` documents the initial speech-recognition and timing process. Its original batch WAV inputs are scratch files; rerunning that initial alignment is not necessary for ordinary visual edits. The already reviewed timeline is in `timing.json`.

## License and attribution

Please retain `Hollywood_Credits_8min.md` or an accessible equivalent when reusing the video. Some photographs require attribution and ShareAlike. The visual adaptation is CC BY-SA 4.0; the music is CC BY 4.0 under the current publisher credit template. Original public-domain photos remain public domain. No endorsement by the featured people is implied.

## Revision V2

The music bed is more prominent (approximately +4.44 dB relative to narration in ducked passages at the mixing stage), with a small speech-preserving EQ cut. Six reveal masks, a subtle chapter light-leak and border highlights replace the four-reveal treatment of V1. Narration, photo selections, dates and subtitle timings remain unchanged. See `output/Nang_cap_V2.md`.

V1 renderer/mixer scripts are retained in `versions/v1/` for reference. The current delivery is V2.

Some large JPEG working copies were storage-optimized after the V2 master was encoded. Dimensions, crop coordinates and source/attribution metadata are unchanged. Original URLs are retained in `actors.json`; the final video is unaffected.

## Working-source archive after the new actresses episode

The completed V2 MP4 is retained unchanged. To keep both full-length deliveries within the workspace budget, the editable photograph copies, original FLAC narration and original-score MP3 were moved into the working cache. A compact separate narration master remains in `audio/Narration_English.opus`. Source/attribution URLs and reviewed crop coordinates remain in the JSON manifests. Rebuilding from scratch requires restoring/re-downloading those photo/score working inputs; the previously listed rendering commands assume they are present.

The older compact narration working stem was also moved to the working cache during the actresses restyle. The self-contained V2 video and its original source/credit records remain preserved.

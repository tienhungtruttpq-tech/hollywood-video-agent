# Hollywood Actresses — enhanced motion/font/hook edit

This revision responds to the requested animated background, more attractive typography and a stronger opening. It keeps the same 24 actresses, 48 dated photographs, selected English narrator and 480-second program.

## Current deliverables

- `output/Hollywood_Actresses_8min_Enhanced.mp4`
- `output/Actresses_Enhanced_EN.srt`
- `output/Thumbnail_A_Enhanced.jpg`
- `output/Thumbnail_B_Enhanced.jpg`
- `output/Actresses_Enhanced_Upload_Kit.zip`
- `output/YouTube_Publish_Kit_Enhanced.md`
- `output/Style_Update_Notes.md`
- `output/Actresses_Credits.md`

## Changes

- Original animated violet/cyan light ribbons and bokeh below the text, with a very subtle moving backdrop behind the layout.
- Outfit ExtraBold headings, title-case names, a gentle headline entrance, gold accent and Manrope SemiBold captions.
- Captions sit in a translucent dark rounded panel. Long captions are balanced to avoid a lonely word on the second line.
- New spoken hook: “You know these faces. Can you name them?”
- The opening uses two seconds of real archival-photo montage, followed by a full three-second first guess. The first name reveal begins at 00:05; the second remains at 00:25. The first comparison is shortened by two seconds so all subsequent timings and the full 8:00 remain intact.

## Production records

- `timing_enhanced.json` is the current narration/caption timeline.
- `prepare_refresh.py` creates the new hook placement and music/voice mix.
- `render_enhanced.py` renders the updated design.
- `create_restyle.py` records the changes from the original renderer.
- `make_packaging_enhanced.py` makes matching thumbnails and credits.
- `validate_enhanced.py` checks the finished MP4, including real pixel changes in the animated footer.
- `work/validation_enhanced.json` records final technical validation.
- `audio/Actresses_Narration_Enhanced.opus` retains a compact, music-free narrator master.

Large temporary media are in `/home/user/.cache/hollywood_actresses_refresh/`. Original photo working copies/prepared crops are in the prior episode’s cache; `actors.json` and `framing.json` retain their source and crop records. Temporary cache material is not part of the permanent delivery. The final MP4 is self-contained.

Earlier episode scripts/timelines are kept in `versions/quiz_original/` as a production reference. Use the Enhanced SRT with this version; the previous SRT has different opening timings.

## Font and source terms

Outfit is from the Google Fonts repository (`ofl/outfit/`) under the SIL Open Font License. Its font/license files are included in `assets/fonts/`. The shared Manrope font is also OFL. Photo and music attributions remain in `Actresses_Credits.md`; no AI aging, face replacement or fabricated celebrity footage was added.

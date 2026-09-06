# Production state — Hollywood Actresses episode

User selected **Hollywood actresses** for a genuinely new second video. Keep approximately eight minutes and English narration/subtitles, using the previously selected voice-00. Deliver a finished MP4 plus title/thumbnail options and an honest testing plan; no claim of guaranteed virality.

## Creative direction
- A three-second name-the-actress challenge before each reveal.
- Start with a portrait immediately; first answer at about three seconds, not a long logo intro.
- Real, licensed early/later photographs with their actual years, no AI aging.
- New female cast; no recycling the previous male-actor program.
- Short original career observations, not repeated reading of dates.
- Four short rounds, meaningful scene motion, bigger concise captions, a simple score-comment prompt.
- Round-only chapters avoid spoiling answers.
- Prefer 24 strong, verifiably sourced actresses over filling slots with weak or out-of-date photos.

## Asset and storage plan
- New project metadata/scripts/deliverables: `/home/user/hollywood_actresses/`.
- Large temporary images/audio/video: `/home/user/.cache/hollywood_actresses/`.
- Preserve the existing completed V2 MP4. The user asked for another video, not a replacement.
- Plan compact encoding for this still-image/quiz program and retain primary deliverables within the workspace snapshot budget; intermediate/source working copies may be cached.

## Research
YouTube guidance emphasizes matching the first 30 seconds to the title/thumbnail and moving compelling later moments earlier. Native title/thumbnail A/B tests choose by watch-time performance rather than CTR alone. Actual improvement needs channel analytics; the episode design and packaging are testable hypotheses, not measured results.

## Current work
The final cast is 24 actresses with 48 selected photographs in `actors.json`. Angelina Jolie uses 2004; Natalie Portman and Anne Hathaway use 2006; Meryl Streep uses a dated 1978 TV publicity photo. All 2026 source dates have been checked to precede September 5, 2026. Six new voice-00 speech batches have been generated in the cache. Narration alignment/mixing and reviewed framing are next. No final episode MP4 has been created yet.

## Updated status
- All 48 source-matched photographs are downloaded, cropped and visually reviewed. Julia, Meg Ryan and Sharon Stone received manual framing; Anne Hathaway now uses a clearer 2008 photograph.
- Six new narration batches plus a short opening replacement have been generated with voice-00 (7 speech calls this turn). Speech alignment, subtitles and the full 480-second audio mix are complete.
- The three-second opening says “Name this actress.” Its short replacement is recorded in `audio_overrides.json`.
- The main actress narration runs at its natural generated rate; only the brief round labels are mildly time-fitted.
- The new quiz renderer has been previewed. Full video rendering is next.

## Completed
The new actresses MP4 is rendered, fully decoded and checked: 480.0 s, 1280×720, 24 fps, 11,520 frames, 26,274,177 bytes, 92 valid subtitle cues. Final AAC was remastered for headroom: -16.5 LUFS, -2.9 dBFS true peak. Two 1280×720 thumbnails, the publication/testing kit, full photo/music credits and SRT are complete. The previous male-actor V2 MP4 is retained. No public YouTube upload or audience test was performed.

## Current requested restyle
User requested an animated lower background, a more attractive font, and a stronger opening. Implemented Outfit ExtraBold headlines, stronger caption styling, animated purple/cyan light ribbons with subtle backdrop motion, and a new voice-00 hook (“You know these faces. Can you name them?”). Opening setup 0–2 s, first guess 2–5 s, first reveal starts 5 s. The first story is shortened by 2 s to preserve 480 s. Rendering with process `video-n-minh-tinh-n-n-ng-v-hook--15021206`; main output will be `Hollywood_Actresses_8min_Enhanced.mp4`. New subtitle/thumbnail/package files prepared. Final encoded validation is pending. One new speech call used this turn.

## Restyle completed
Final file: `output/Hollywood_Actresses_8min_Enhanced.mp4`, 30,394,252 bytes. Full decode/92 captions/480 seconds passed. Encoded footer motion verified; final typography/intro/credits reviewed. First montage 0–2 s; first guess 2–5 s; first name reveal begins at 5 s. Outfit ExtraBold/Manrope SemiBold with a dark caption card. Updated thumbnails and publication ZIP are ready. The earlier actresses version and older narration stem were archived in the working cache; the separate male-actor V2 MP4 remains unchanged.

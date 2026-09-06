from pathlib import Path
import json,re,html,importlib.metadata
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
actors=json.loads((ROOT/'actors.json').read_text());narr=json.loads((ROOT/'narrative.json').read_text())

def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]+>','',html.unescape(html.unescape(s)))).strip()
def stamp(t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
lines=['# Hollywood THEN & NOW — eight-minute edition','',
'**30 actors · 60 dated source photographs · English narration and captions.**','',
'**V2 update:** same source photographs and narration; six reveal masks, a graphic light-leak, lightly equalized/rebalanced music and original stereo transition accents.','','## How the dates are used','',
'- The years on screen are the years of the selected photographs, not birth years or ages.',
'- “NOW” means the later dated photograph in each comparison. It does **not** mean that every photograph was taken in 2026.',
'- The displayed gap is the difference between the two calendar years; it is not a claim about an exact number of days.',
'- Source photos span 1984–2026. The 2026 selections predate September 5, 2026.',
'- Some early snapshots are small, grainy or softly focused. No AI face restoration, synthetic aging, face replacement or generated celebrity footage was used.',
'- The reference video inspired the comparison concept; none of its footage, stills or soundtrack was reused.','',
'## Music — required credit','',
'> “Dream Culture” — Kevin MacLeod (incompetech.com)  \n> Licensed under Creative Commons: By Attribution 4.0 License  \n> https://creativecommons.org/licenses/by/4.0/','',
'- Track page: https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300046',
'- Publisher track metadata: https://incompetech.com/music/royalty-free/pieces.json (ISRC USUAN1300046).',
'- Download: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dream%20Culture.mp3',
'- The current publisher page’s credit template specifies CC BY 4.0. The supplied MP3 identifies Kevin MacLeod as composer/artist.',
'- This edit repeats and crossfades the instrumental track, changes its level under dialogue, and adds fades. It does not reproduce the reference video’s soundtrack.',
'- Short transition swishes are original, procedurally generated sound accents.','',
'## Narration, typography and visual adaptation','',
'- Original English script, delivered in the user-selected synthetic narration voice. The narrator is not an imitation or recording of any featured actor.',
'- English captions are burned into the comparison cards, introduction and ending. The companion SRT also covers all spoken narration.',
'- Fonts: Bebas Neue and Manrope, distributed under the SIL Open Font License. License texts are included in `assets/fonts/`.',
'- Adaptations to the photographs: selection, cropping, resizing, compositing, small digital pans/zooms, transition masks, graphic overlays and on-screen credit strips. Photographic faces were not synthesized or retouched.',
'- The visual adaptation/arrangement is offered under **CC BY-SA 4.0**: https://creativecommons.org/licenses/by-sa/4.0/. Original photographs retain the licenses listed below; public-domain source material remains public domain. The music retains its own CC BY 4.0 terms.',
'- Reuse the video with this credits document or an accessible equivalent that preserves attribution, source and license information. Share-alike conditions apply where required by the source licenses.',
'- Open licenses do not imply endorsement by the people shown, waive every personality/trademark right, or guarantee a particular platform’s monetization or Content ID decision.','',
'## Chapter index','',
'| Time | Actor | THEN → later photo | Year gap |','|---|---|---|---:|']
for i,a in enumerate(actors):lines.append(f'| {stamp(10+15*i)} | {a["name"]} | {a["years"][0]} → {a["years"][1]} | {a["delta"]} |')
lines += ['','Introduction: 00:00–00:10. Comparisons: 00:10–07:40. Ending: 07:40–07:50. Credits: 07:50–08:00.','','## Photograph-by-photograph attribution','']
for i,a in enumerate(actors):
    lines += [f'### {i+1:02d}. {a["name"]} — {stamp(10+i*15)}','']
    for era,label in [('then','THEN'),('now','LATER / NOW')]:
        p=a[era];artist=clean(p['artist'])
        if i==2 and era=='now':artist='Benjamin Applebaum / Department of Defense; published by the Chairman of the Joint Chiefs of Staff'
        if i==21 and era=='then':artist='Public-domain White House archive (the source Artist field contains a public-domain statement)'
        lines += [f'**{label} — {p["year"]}**',
                  f'- File: {p["title"].replace("File:","")}',
                  f'- Creator/source credit: {artist}',
                  f'- License: {p["license"]}'+(f' — {p["license_url"]}' if p.get('license_url') else ' — see the source page for its public-domain statement.'),
                  f'- Source: {p["source"]}',
                  f'- Source date field: {clean(p.get("date", "")) or "See the dated source description/file title."}',
                  f'- Source description: {clean(p["description"])}',
                  '- Used as a cropped/resized animated still; not a newly photographed or AI-aged appearance.','']
    url='https://en.wikipedia.org/wiki/'+a['name'].replace(' ','_')
    lines += [f'Career-note reference: {url}','']
lines += ['## Additional film-context references','',
'https://en.wikipedia.org/wiki/Ocean%27s_Eleven_(2001_film)','',
'https://en.wikipedia.org/wiki/The_Proposal_(2009_film)','',
'## Production record','',
'The project retains the chosen photo metadata in `actors.json`, the narration in `narrative.json`, reviewed crop rectangles in `framing.json`, and audio/caption placements in `timing.json`. Technical validation is recorded in `work/validation.json` after export.','']
(OUT/'Hollywood_Credits_8min.md').write_text('\n'.join(lines))
requirements=['Pillow','numpy','scipy','opencv-python-headless','imageio-ffmpeg','requests','beautifulsoup4','faster-whisper']
res=[]
for name in requirements:
    try:res.append(name+'=='+importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:res.append(name)
(ROOT/'requirements.txt').write_text('\n'.join(res)+'\n')
print('Credits and requirements saved.')

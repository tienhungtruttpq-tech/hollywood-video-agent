from pathlib import Path
import json,html,re,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageOps
import render_episode as r
ROOT=r.ROOT;OUT=r.OUT

def gradient_bottom(im,start=340,end_alpha=.95):
 a=np.asarray(im,dtype=np.float32);f=np.clip((np.arange(im.height)-start)/(im.height-start),0,1).astype(np.float32)[:,None,None]*end_alpha
 return Image.fromarray(np.clip(a*(1-f)+np.array(r.BG)[None,None,:]*f,0,255).astype(np.uint8))

def make_thumbnails():
 # A tests the direct before/after promise; both photos appear in the opening.
 a=Image.new('RGB',(1280,720),r.BG)
 a.paste(ImageOps.fit(r.square(0,'then'),(632,720),Image.Resampling.LANCZOS,centering=(.56,.22)),(0,0))
 a.paste(ImageOps.fit(r.square(0,'now'),(632,720),Image.Resampling.LANCZOS,centering=(.52,.25)),(648,0))
 a=gradient_bottom(a,358,.98);d=ImageDraw.Draw(a)
 d.rectangle((630,0,649,720),fill=r.BG)
 for x,label in [(35,'THEN / 1990'),(684,'NOW / 2025')]:
  d.rounded_rectangle((x,30,x+195,77),radius=8,fill=r.BG)
  r.text(d,(x+18,40),label,24,r.CREAM,weight=750)
 phrase='NAME HER IN 3 SECONDS';sz=108
 while r.font(sz,'display').getlength(phrase)>1190:sz-=1
 r.text(d,(640,537),phrase,sz,r.GOLD,'display',anchor='mt')
 r.track(d,(640,665),'24 HOLLYWOOD ACTRESSES',15,3.0,r.CREAM,'center')
 r.text(d,(12,702),'Photos: Roland Godefroy / Colleen Sturtevant. Source & license details: Actresses_Credits.md',9,r.MUTED)
 a.save(OUT/'Thumbnail_A_Then_Now.jpg',quality=94,optimize=True)
 # B tests a cleaner quiz-first approach, not a trivial color variation of A.
 b=Image.new('RGB',(1280,720),r.BG)
 b.paste(ImageOps.fit(r.square(1,'then'),(798,720),Image.Resampling.LANCZOS,centering=(.49,.30)),(0,0))
 b=gradient_bottom(b,470,.92);d=ImageDraw.Draw(b)
 d.rectangle((798,0,1280,720),fill=r.BG);d.rectangle((798,0,806,720),fill=r.GOLD)
 r.track(d,(1043,43),'THE 24-STAR QUIZ',18,2.1,r.CREAM,'center')
 d.ellipse((930,110,1156,336),outline=r.GOLD,width=9)
 r.text(d,(1043,120),'3',222,r.CREAM,'display',anchor='mt')
 r.track(d,(1043,363),'SECONDS',23,5,r.LAV,'center')
 r.text(d,(1043,442),'NAME THE',80,r.CREAM,'display',anchor='mt')
 r.text(d,(1043,532),'ACTRESS',98,r.GOLD,'display',anchor='mt')
 r.text(d,(48,567),'24 / 24?',117,r.CREAM,'display')
 r.text(d,(16,701),'Photo: Stefan Servos / CC BY-SA 3.0. Full credit: Actresses_Credits.md',9,r.MUTED)
 b.save(OUT/'Thumbnail_B_Quiz.jpg',quality=94,optimize=True)
 # Inspection only: readability at a small, mobile-feed-like size.
 sheet=Image.new('RGB',(640,205),r.BG)
 for j,im in enumerate([a,b]):sheet.paste(im.resize((320,180),Image.Resampling.LANCZOS),(320*j,0))
 dd=ImageDraw.Draw(sheet);r.text(dd,(12,184),'A / DIRECT COMPARISON',11,r.CREAM);r.text(dd,(332,184),'B / QUIZ-FIRST',11,r.CREAM)
 sheet.save(r.WORK/'thumbnail_mobile_check.jpg',quality=93)
 print('Two thumbnails created.')

def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]+>','',html.unescape(html.unescape(s or '')))).strip()
def tc(t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
def write_credits():
 a=r.ACTORS
 lines=['# Hollywood Actresses THEN / NOW — quiz episode credits','',
 '**24 actresses · 48 source photographs · original English quiz/commentary.**','',
 '## Editorial notes','',
 '- The dates shown are photograph years, not birth years or ages. “NOW” means the selected later photograph, not that all images were taken in 2026.',
 '- The gap is the difference between the two calendar years, not a claim about exact elapsed days.',
 '- Photographs span 1978–2026. Every 2026 selection predates September 5, 2026.',
 '- The image sources include public appearances, on-set photographs, a television publicity photograph and a yearbook photograph. These contexts are marked where relevant. Styles, costumes, lighting and camera angles differ.',
 '- No AI aging, face replacement, fabricated celebrity motion or AI face restoration was used. Source images are cropped, resized and composed with soft side extensions and graphic transition masks.',
 '- The three-second challenge is a passive video quiz: viewers keep their own score. The on-screen question counter does not claim to know which answers a viewer got right.',
 '- Short comments about performance style are original editorial observations. Named film credits/roles/awards are grounded in the linked biographical sources.',
 '- No footage, screenshots or audio from the YouTube reference video was reused.','',
 '## Music — required attribution','',
 '> “Dream Culture” — Kevin MacLeod (incompetech.com)  \n> Licensed under Creative Commons: By Attribution 4.0 License  \n> https://creativecommons.org/licenses/by/4.0/','',
 'Track page: https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300046','',
 'Publisher metadata: https://incompetech.com/music/royalty-free/pieces.json — ISRC USUAN1300046.','',
 'The current publisher credit template specifies CC BY 4.0. This edit loops/crossfades, equalizes, ducks and fades the track. Gentle countdown ticks/reveal tones are original synthetic sound accents.','',
 '## Narration, typography and reuse','',
 '- English narration is synthesized using the voice previously selected by the user. It is not a recording or imitation of any actress.',
 '- Fonts: Bebas Neue and Manrope, SIL Open Font License.',
 '- The visual adaptation/arrangement, including the two thumbnail adaptations, is offered under **CC BY-SA 4.0**: https://creativecommons.org/licenses/by-sa/4.0/. The original photographs keep their listed licenses; public-domain material remains public domain. Music retains CC BY 4.0.',
 '- Keep creator, source and license information accessible when publishing/reusing. Do not relabel the whole work as plain CC BY if you do not have the rights to remove applicable ShareAlike requirements.',
 '- Open licenses do not imply endorsement, waive every personality/trademark right, or guarantee platform monetization/Content ID outcomes.','',
 '## Thumbnail attribution','',
 '- Thumbnail A uses Julia Roberts’s two listed photographs (items 01 THEN / NOW).',
 '- Thumbnail B uses Angelina Jolie’s listed early photograph (item 02 THEN).',
 '- Both use only real source photographs, with cropping and original graphic text; no invented before/after appearance.','',
 '## Source photographs and answer key','',
 '*This section contains quiz answers. Round-only chapters are used in the video so chapter labels do not reveal answers early.*','']
 for i,x in enumerate(a):
  p=r.APART[i];start=0 if i==0 else p['start']
  lines += [f'### {i+1:02d}. {x["name"]} — {tc(start)}','']
  for era,title in [('then','THEN'),('now','LATER / NOW')]:
   ph=x[era]
   lines += [f'**{title} / {ph["year"]}**',f'- File: {ph["title"].replace("File:","")}',f'- Creator: {clean(ph["artist"])}',f'- License: {ph["license"]}'+(f' — {ph["license_url"]}' if ph.get('license_url') else ' — see the public-domain statement on the source page.'),f'- Source: {ph["source"]}',f'- Date field: {clean(ph["date"]) or "See the dated file description."}',f'- Description/context: {clean(ph["description"])}','- Use: source-matched crop/resize/composite; no generated facial details.','']
  lines += ['Career reference: https://en.wikipedia.org/wiki/'+x['name'].replace(' ','_'),'']
 lines += ['Additional character-credit reference: https://en.wikipedia.org/wiki/The_Dark_Knight_Rises','',
 'Production metadata: `actors.json`, `framing.json`, `narrative.json`, `audio_overrides.json`, and `timing.json`. Final technical validation is recorded after encoding.','']
 (OUT/'Actresses_Credits.md').write_text('\n'.join(lines))
 print('Full photo, music and thumbnail credits written.')

if __name__=='__main__':make_thumbnails();write_credits()

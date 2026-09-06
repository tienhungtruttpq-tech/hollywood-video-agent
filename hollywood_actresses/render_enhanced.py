#!/usr/bin/env python3
"""A genuine second episode: 24 actresses, a 3-second quiz and role commentary."""
from pathlib import Path
import json,math,subprocess,argparse,concurrent.futures,hashlib,re,html
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageFilter
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_actresses_refresh');PREP=Path('/home/user/.cache/hollywood_actresses/prepared');WORK=CACHE/'render';WORK.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();W,H,FPS,TOTAL=1280,720,24,480.
BG=(16,17,25);CREAM=(246,242,235);LAV=(193,174,245);GOLD=(232,200,153);MUTED=(149,149,165);LINE=(51,48,68)
PX=(58,712);PY=133;PW=510;PH=440
ACTORS=json.loads((ROOT/'actors.json').read_text())
DATA=json.loads((ROOT/'timing_enhanced.json').read_text());PARTS=DATA['parts'];BYID={p['id']:p for p in PARTS}
APART=[BYID[f'actress_{i:02d}'] for i in range(24)]
ROUND_NAMES=['THE OPENING SIX','MOVIE MEMORIES','CHANGING ROLES','THE FINAL SIX']
FONT_DIR=Path('/home/user/hollywood_full/assets/fonts')
FONTS={};cv2.setNumThreads(1)
OUTFIT=ROOT/'assets/fonts/Outfit.ttf'

def font(size,face='sans',weight=600):
 key=(int(size),face,weight)
 if key not in FONTS:
  path=OUTFIT if face=='display' else FONT_DIR/'Manrope.ttf'
  f=ImageFont.truetype(str(path),int(size))
  try:f.set_variation_by_axes([800 if face=='display' else weight])
  except Exception:pass
  FONTS[key]=f
 return FONTS[key]
def text(d,xy,s,size=20,fill=CREAM,face='sans',weight=600,anchor=None):
 d.text(xy,s,font=font(size,face,weight),fill=fill,anchor=anchor)

def track(d,xy,s,size=10,spacing=1.6,fill=MUTED,anchor='left'):
 f=font(size,weight=650);width=sum(d.textlength(ch,font=f) for ch in s)+spacing*max(0,len(s)-1);x,y=xy
 if anchor=='center':x-=width/2
 if anchor=='right':x-=width
 for ch in s:d.text((x,y),ch,font=f,fill=fill);x+=d.textlength(ch,font=f)+spacing
 return width

def ease(x):x=max(0.,min(1.,x));return x*x*(3-2*x)
def wrapped(s,width,size):
 out=[];line='';f=font(size)
 for word in s.split():
  new=(line+' '+word).strip()
  if line and f.getlength(new)>width:out.append(line);line=word
  else:line=new
 if line:out.append(line)
 return out

# A static background avoids distracting grain shimmer and needless bitrate.
yy,xx=np.mgrid[0:H,0:W];g=np.exp(-(((xx-640)/950)**2+((yy-220)/740)**2)*2)
a=np.empty((H,W,3),np.uint8)
for k,c in enumerate(BG):a[:,:,k]=c+g*[3,3,8][k]
BACKGROUND=Image.fromarray(a);del a,g,yy,xx
PHOTOS={};SQUARE={};BASES={};PLACEHOLDER=None;CAPTIONS={};CREDIT_PAGES={};ROUND_PAGES={}
FLOW_CACHE={};WASH_CACHE={};HEADLINE_CACHE={};FLOW_Y=596

def flow_strip(t):
 # Eight-second loop, generated at half resolution: smooth and inexpensive.
 key=int(t*FPS+.001)%(8*FPS)
 if key not in FLOW_CACHE:
  h=(H-FLOW_Y)//2;w=W//2
  yy,xx=np.mgrid[0:h,0:w].astype(np.float32);x=xx/w;y=yy/h
  phase=2*np.pi*key/(8*FPS)
  rise=np.clip(y/.28,0,1)
  line1=.53+.14*np.sin(2*np.pi*x+phase)
  line2=.83+.09*np.sin(4*np.pi*x-2*phase)
  band1=np.exp(-((y-line1)/.16)**2)*.46*rise
  band2=np.exp(-((y-line2)/.13)**2)*.29*rise
  strip=np.empty((h,w,3),np.float32);strip[:]=np.array(BG,np.float32)
  for alpha,color in [(band1,[111,65,174]),(band2,[32,118,132])]:
   strip=strip*(1-alpha[:,:,None])+np.array(color,np.float32)*alpha[:,:,None]
  for j in range(5):
   cx=.5+.53*np.sin(phase+j*1.31);cy=.60+.20*np.cos(phase*2+j)
   glow=np.exp(-(((x-cx)/(.035+.009*j))**2+((y-cy)/.27)**2))*rise*.14
   color=np.array([217,151,82] if j%2 else [151,99,212],np.float32)
   strip=strip*(1-glow[:,:,None])+color*glow[:,:,None]
  FLOW_CACHE[key]=Image.fromarray(np.clip(strip,0,255).astype(np.uint8))
 return FLOW_CACHE[key].resize((W,H-FLOW_Y),Image.Resampling.BILINEAR)

def base_wash(k):
 if k not in WASH_CACHE:
  h,w=180,320;yy,xx=np.mgrid[0:h,0:w].astype(np.float32);x=xx/w;y=yy/h;phase=2*np.pi*k/16
  image=np.asarray(BACKGROUND.resize((w,h),Image.Resampling.BILINEAR),dtype=np.float32)
  glow=np.exp(-(((x-(.45+.20*np.sin(phase)))/.48)**2+((y-(.22+.13*np.cos(phase)))/.52)**2))*.048
  image=image*(1-glow[:,:,None])+np.array([105,67,157],np.float32)*glow[:,:,None]
  WASH_CACHE[k]=Image.fromarray(np.clip(image,0,255).astype(np.uint8))
 return WASH_CACHE[k]

def animated_background(t):
 position=(t%8)*2;k=int(position)%16;fraction=position-int(position)
 im=Image.blend(base_wash(k),base_wash((k+1)%16),fraction).resize((W,H),Image.Resampling.BILINEAR)
 im.paste(flow_strip(t),(0,FLOW_Y));return im

def with_flow(im,t):
 region=im.crop((0,FLOW_Y,W,H));im.paste(Image.blend(region,flow_strip(t),.89),(0,FLOW_Y));return im

def headline(im,i,guess,local):
 phrase='Know this face?' if guess else ACTORS[i]['name']
 key=(i,guess)
 if key not in HEADLINE_CACHE:
  layer=Image.new('RGBA',(W,118));d=ImageDraw.Draw(layer)
  size=54 if guess else 52
  while font(size,'display').getlength(phrase)>1110:size-=1
  # A restrained shadow and a gold underline give the heavier face depth.
  text(d,(642,46),phrase,size,(0,0,0,155),'display',anchor='mt')
  text(d,(640,43),phrase,size,CREAM+(255,),'display',anchor='mt')
  if not guess:d.rounded_rectangle((574,98,706,101),radius=2,fill=GOLD+(240,))
  HEADLINE_CACHE[key]=layer
 layer=HEADLINE_CACHE[key]
 if not guess:
  e=ease((local-(3. if i else 0.))/.28)
  if e<1:
   layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*e)))
  dy=round(5*(1-e))
 else:dy=0
 im.paste(layer,(0,dy),layer)
 return im


def square(i,era):
 key=(i,era)
 if key not in SQUARE:SQUARE[key]=Image.open(PREP/f'{i:02d}_{era}.jpg').convert('RGB')
 return SQUARE[key]
def photo(i,era):
 key=(i,era)
 if key not in PHOTOS:
  src=square(i,era)
  # Preserve all of the reviewed square crop. Soft side extensions fill the
  # slightly wider panel without cutting a forehead or chin.
  back=ImageOps.fit(src,(PW,PH),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(22))
  back=Image.blend(back,Image.new('RGB',back.size,BG),.58)
  sharp=src.resize((PH,PH),Image.Resampling.LANCZOS);back.paste(sharp,((PW-PH)//2,0));PHOTOS[key]=back
 return PHOTOS[key]
def blank():
 global PLACEHOLDER
 if PLACEHOLDER is None:
  im=Image.new('RGB',(PW,PH),(27,25,39));d=ImageDraw.Draw(im)
  for x in range(-440,520,40):d.line((x,0,x+440,440),fill=(39,35,54),width=1)
  track(d,(PW/2,110),'THINK OF HER MOVIES',11,2,LAV,'center')
  text(d,(PW/2,155),'?',154,CREAM,'display',anchor='mt')
  track(d,(PW/2,339),'NAME REVEAL',11,2.2,MUTED,'center')
  PLACEHOLDER=im
 return PLACEHOLDER

def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]*>','',html.unescape(html.unescape(s or '')))).strip()
def credit(i,era):
 p=ACTORS[i][era];s=clean(p['artist'])
 if len(s)>53:s=s[:50].rstrip()+'…'
 return s+'  /  '+p['license']

def layout(i,guess):
 key=(i,guess)
 if key not in BASES:
  a=ACTORS[i];p=APART[i];im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
  track(d,(58,22),'THE SCREEN ARCHIVE / MOVIE STAR QUIZ',10,1.6)
  track(d,(1222,22),f'ROUND {i//6+1} / 4   •   QUESTION {i+1:02d} / 24',11,1.2,CREAM,'right')
  title='NAME THE ACTRESS' if guess else a['name'].upper()
  # The larger Outfit headline is composited/animated in card().
  for era,x in [('then',PX[0]),('now',PX[1])]:
   text(d,(x,102),'THEN' if era=='then' else 'NOW',25,LAV if era=='then' else GOLD,'display')
   text(d,(x+PW,105),str(a[era]['year']),21,CREAM,weight=650,anchor='rt')
   d.rectangle((x-1,PY-1,x+PW,PY+PH),outline=LINE,width=1)
   if not guess:
    s=credit(i,era);sz=10
    if font(sz).getlength(s)>PW:sz=9
    text(d,(x,PY+PH+7),s,sz,MUTED)
  if not guess:
   text(d,(640,295),str(a['delta']),46,GOLD,'display',anchor='mt')
   track(d,(640,353),'PHOTO',9,1.5,MUTED,'center');track(d,(640,369),'YEARS APART',8,1,MUTED,'center')
   d.line((613,400,667,400),fill=LINE,width=1);d.line((661,396,667,400,661,404),fill=GOLD,width=1)
   roles=' / '.join(p['films'])
   sz=12
   while font(sz).getlength(roles)>1110:sz-=1
   text(d,(640,605),roles,sz,LAV,anchor='mt')
  else:
   track(d,(640,606),'FIRST GUESS / 3 SECONDS' if i==0 else 'ROLE CLUE',10,2.0,LAV,'center')
  track(d,(640,702),'REAL, DATED PHOTOS / "NOW" = LATER PHOTO / NO AI AGING',8,1.1,(116,116,137),'center')
  BASES[key]=im
 return BASES[key].copy()

def caption(text_value):
 if text_value not in CAPTIONS:
  sz=24;lines=wrapped(text_value,1110,sz)
  while len(lines)>2 and sz>20:sz-=1;lines=wrapped(text_value,1110,sz)
  if len(lines)==2 and font(sz).getlength(lines[1]) < .42*font(sz).getlength(lines[0]):
   words=text_value.split();candidates=[]
   for j in range(1,len(words)):
    one=' '.join(words[:j]);two=' '.join(words[j:]);w1=font(sz).getlength(one);w2=font(sz).getlength(two)
    if max(w1,w2)<=1110:
     cost=abs(w1-w2)
     if one.endswith((',',':',';','—')):cost*=.65
     candidates.append((cost,one,two))
   if candidates:
    _,one,two=min(candidates);lines=[one,two]
  im=Image.new('RGBA',(W,74));d=ImageDraw.Draw(im)
  d.rounded_rectangle((46,0,1234,72),radius=17,fill=(6,8,17,130),outline=(192,170,246,75),width=1)
  top=10 if len(lines)==2 else 20
  for j,line in enumerate(lines):
   text(d,(641,top+j*(sz+6)+1),line,sz,(0,0,0,185),weight=600,anchor='mt')
   text(d,(640,top+j*(sz+6)),line,sz,CREAM+(255,),weight=600,anchor='mt')
  CAPTIONS[text_value]=im
 return CAPTIONS[text_value]

def reveal(i,q):
 if q>=1:return photo(i,'now')
 if q<=0:return blank()
 p=ease(q);left=np.asarray(blank()).astype(np.float32);right=np.asarray(photo(i,'now')).astype(np.float32)
 # Fade the placeholder lettering away quickly rather than stamping it over a face.
 simple=Image.new('RGB',(PW,PH),(27,25,39));d=ImageDraw.Draw(simple)
 for x in range(-PH,PW,40):d.line((x,0,x+PH,PH),fill=(39,35,54),width=1)
 fade=ease(q/.22);left=left*(1-fade)+np.asarray(simple)*fade
 mode=i//6
 if mode==0:
  mask=np.clip(((PW+28)*p-14-np.arange(PW))/16,0,1)[None,:,None]
 elif mode==1:
  mask=np.clip(((PW/2+24)*p-10-np.abs(np.arange(PW)-PW/2))/15,0,1)[None,:,None]
 elif mode==2:
  yy,xx=np.mgrid[0:PH,0:PW];plane=(xx/PW+.55*yy/PH)/1.55;mask=np.clip((1.1*p-.025-plane)/.05,0,1)[:,:,None]
 else:
  yy,xx=np.mgrid[0:PH,0:PW];dist=np.sqrt((xx-PW/2)**2+(yy-PH*.46)**2);mask=np.clip((380*p-12-dist)/16,0,1)[:,:,None]
 return Image.fromarray(np.clip(right*mask+left*(1-mask),0,255).astype(np.uint8))

def current_caption(part,t):
 return next((c['text'] for c in part['captions'] if c['start']<=t<c['end']),None)

def card(i,local,t,cold_open=False):
 p=APART[i];guess=cold_open or (i>0 and local<3.)
 im=animated_background(t);overlay=layout(i,guess);im.paste(overlay,(0,0),overlay);im.paste(photo(i,'then'),(PX[0],PY))
 if guess:im.paste(blank(),(PX[1],PY))
 else:im.paste(reveal(i,(local-(3. if i>0 else 0.))/.58),(PX[1],PY))
 d=ImageDraw.Draw(im)
 for x in PX:d.rectangle((x-1,PY-1,x+PW,PY+PH),outline=LINE,width=1)
 if guess:
  elapsed=local;remaining=max(1,3-int(elapsed));q=max(0,min(1,elapsed/3))
  d.ellipse((596,301,684,389),outline=LINE,width=2)
  d.arc((596,301,684,389),start=-90,end=-90+360*(1-q),fill=GOLD,width=4)
  text(d,(640,320),str(remaining),57,CREAM,'display',anchor='mt')
  track(d,(640,403),'SECONDS',9,1.5,MUTED,'center')
  c=current_caption(BYID['intro'],t) if cold_open else None
  layer=caption(c or p['hint']);im.paste(layer,(0,625),layer)
 else:
  c=current_caption(p,t)
  if c:
   layer=caption(c);im.paste(layer,(0,625),layer)
  elif local>=p['duration']-2.55:
   if i==23:s='Your final score?  /  24'
   elif (i+1)%6==0:s='NEXT ROUND  /  '+ROUND_NAMES[(i+1)//6]
   else:s='NEXT CLUE  /  '+APART[i+1]['hint']
   layer=caption(s);im.paste(layer,(0,625),layer)
  # Context labels apply to photographed roles/archives, not to biological ages.
  for era,x in [('then',PX[0]),('now',PX[1])]:
   context=ACTORS[i][era].get('context','')
   if context:
    w=font(10).getlength(context.upper())+18
    d.rectangle((x+8,PY+8,x+8+w,PY+29),fill=(22,21,30))
    text(d,(x+17,PY+11),context.upper(),10,CREAM,weight=650)
 im=headline(im,i,guess,local)
 return im

def photo_montage(ids):
 im=Image.new('RGB',(W,H));widths=[214,213,213,213,213,214];x=0
 for i,w in zip(ids,widths):
  src=ImageOps.fit(square(i,'now'),(w,H),Image.Resampling.LANCZOS,centering=(.5,.25));im.paste(src,(x,0));x+=w
 return Image.blend(im,Image.new('RGB',(W,H),BG),.76)

def round_card(p,local):
 n=p['round']
 if n not in ROUND_PAGES:ROUND_PAGES[n]=photo_montage(list(range((n-1)*6,n*6)))
 im=with_flow(ROUND_PAGES[n].copy(),p['start']+local);d=ImageDraw.Draw(im)
 track(d,(640,213),f'{n*6} REVEALED / {24-n*6} TO GO',14,2.5,LAV,'center')
 text(d,(640,262),f'ROUND {n+1}',88,CREAM,'display',anchor='mt')
 track(d,(640,406),ROUND_NAMES[n],15,3.0,CREAM,'center')
 text(d,(640,485),'Keep your score. The next face is coming.',22,CREAM,anchor='mt')
 c=current_caption(p,p['start']+local)
 if c:
  layer=caption(c);im.paste(layer,(0,625),layer)
 return im

def outro(t):
 im=with_flow(photo_montage([0,1,4,18,22,23]),t);d=ImageDraw.Draw(im)
 track(d,(640,175),'TWENTY-FOUR FACES. DECADES OF MOVIE MEMORIES.',12,1.8,LAV,'center')
 text(d,(640,236),'YOUR SCORE / 24?',79,CREAM,'display',anchor='mt')
 text(d,(640,401),'Which face surprised you most?',28,CREAM,anchor='mt')
 text(d,(640,459),'Share your score and the actress you almost missed.',20,MUTED,anchor='mt')
 c=current_caption(BYID['outro'],t)
 if c:
  layer=caption(c);im.paste(layer,(0,625),layer)
 return im

def credits(page):
 if page in CREDIT_PAGES:return CREDIT_PAGES[page].copy()
 im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
 track(d,(58,28),'THE SCREEN ARCHIVE / SOURCES & CREDITS',11,2)
 if page==0:
  text(d,(58,95),'REAL PHOTOS. ORIGINAL QUIZ.',52,CREAM,'display')
  text(d,(58,202),'Dream Culture',45,GOLD,'display')
  text(d,(58,263),'Kevin MacLeod  /  incompetech.com',26,CREAM,weight=650)
  text(d,(58,308),'Music licensed under Creative Commons Attribution 4.0',20,MUTED)
  text(d,(58,346),'creativecommons.org/licenses/by/4.0/',18,LAV)
  d.line((58,407,1222,407),fill=LINE,width=1)
  text(d,(58,443),'Original quiz, role commentary, graphics and countdown sounds.',20,CREAM)
  text(d,(58,487),'English narration generated with the user-selected AI voice.',20,CREAM)
  text(d,(58,531),'48 dated photographs. No AI aging or face replacement.',20,CREAM)
  text(d,(58,626),'Full photo records and reuse terms: Actresses_Credits.md',19,MUTED)
 else:
  text(d,(58,80),'THE PHOTOGRAPHERS & ARCHIVES',44,CREAM,'display')
  text(d,(58,145),'THEN source / later source. Individual licenses and links are in the companion credits.',14,MUTED)
  for col in range(2):
   for row in range(12):
    i=col*12+row;a=ACTORS[i];x=58+col*613;y=205+row*27
    one=clean(a['then']['artist']);two=clean(a['now']['artist'])
    label=f'{i+1:02d}  {a["name"]}: {one} / {two}'
    sz=10
    while font(sz).getlength(label)>554 and sz>8:sz-=1
    while font(sz).getlength(label+'…')>554:label=label[:-1]
    text(d,(x,y),label,sz,CREAM)
  d.line((58,558,1222,558),fill=LINE,width=1)
  text(d,(58,584),'Full attribution: Actresses_Credits.md',21,CREAM)
  text(d,(58,629),'Visual adaptation: CC BY-SA 4.0  /  creativecommons.org/licenses/by-sa/4.0/',15,MUTED)
  text(d,(58,668),'Independent editorial video. No endorsement by the featured people is implied.',14,MUTED)
 CREDIT_PAGES[page]=im.copy();return im

def opening_montage(t):
 i=min(2,int(t/(2/3)))
 im=animated_background(t)
 src=square(i,'then').resize((720,720),Image.Resampling.LANCZOS);im.paste(src,(0,0))
 d=ImageDraw.Draw(im)
 d.rectangle((720,0,W,H),fill=BG);im=with_flow(im,t);d=ImageDraw.Draw(im)
 d.rectangle((716,0,722,H),fill=GOLD)
 track(d,(754,49),'HOLLYWOOD / THEN & NOW',12,1.5,CREAM)
 text(d,(754,197),'You know',71,CREAM,'display')
 text(d,(754,290),'these faces.',71,GOLD,'display')
 text(d,(757,429),'Can you name them?',27,CREAM,weight=650)
 track(d,(757,491),'24 ICONS. 3 SECONDS EACH.',12,1.1,LAV)
 d.rounded_rectangle((25,25,208,66),radius=10,fill=BG)
 text(d,(40,34),str(ACTORS[i]['then']['year'])+' / ARCHIVE',16,CREAM,weight=700)
 c=current_caption(BYID['intro'],t)
 if c:
  layer=caption(c);im.paste(layer,(0,625),layer)
 return im

def frame(t):
 if t<2:im=opening_montage(t)
 elif t<5:im=card(0,t-2,t,True)
 elif t>=470:
  overlay=credits(0 if t<475 else 1);im=animated_background(t);im.paste(overlay,(0,0),overlay)
 elif t>=465:im=outro(t)
 else:
  p=next(p for p in PARTS if p['start']<=t<p['start']+p['duration'])
  if p['kind']=='interlude':im=round_card(p,t-p['start'])
  else:im=card(p['actor'],t-p['start'],t)
 if t>479.6:im=Image.blend(im,Image.new('RGB',(W,H),BG),ease((t-479.6)/.4))
 d=ImageDraw.Draw(im);d.rectangle((0,717,W,719),fill=LINE);d.rectangle((0,717,round(W*t/TOTAL),719),fill=LAV)
 return im

def preview():
 for page in range(3):
  sheet=Image.new('RGB',(1280,1440),BG)
  for j,i in enumerate(range(page*8,page*8+8)):
   t=APART[i]['start']+(6 if i>0 else 3)
   im=frame(t).resize((640,360),Image.Resampling.LANCZOS);sheet.paste(im,((j%2)*640,(j//2)*360))
  sheet.save(WORK/f'layout_{page+1}.jpg',quality=94)
 for t in [.35,1.05,1.65,2.5,4.7,5.2,5.8,10.,10.7,25.8,117.5,465.8,472.]:frame(t).save(WORK/f'frame_{t:.1f}.jpg',quality=93)
 print('EPISODE_PREVIEWS_READY',flush=True)

def encode_part(i):
 dest=WORK/f'part_{i:02d}.mp4';start=i*60;end=start+60
 if dest.exists() and dest.stat().st_size>30000:return str(dest)
 cmd=[FF,'-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-tune','stillimage','-crf','25','-threads','2','-g','96','-keyint_min','24','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
 with open(WORK/f'part_{i:02d}.log','w') as log:
  p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
  try:
   for n in range(start*FPS,end*FPS):p.stdin.write(frame(n/FPS).tobytes())
   p.stdin.close();code=p.wait()
  except BaseException:p.kill();dest.unlink(missing_ok=True);raise
 if code:dest.unlink(missing_ok=True);raise RuntimeError((WORK/f'part_{i:02d}.log').read_text())
 print(f'PART_COMPLETE {i+1}/8 ({dest.stat().st_size/1e6:.1f} MB)',flush=True);return str(dest)

def render(workers):
 checksum=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['render_enhanced.py','actors.json','framing.json','timing_enhanced.json'])).hexdigest();stamp=WORK/'config.sha256'
 if not stamp.exists() or stamp.read_text()!=checksum:
  for old in WORK.glob('part_*.mp4'):old.unlink()
  stamp.write_text(checksum)
 with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:files=list(pool.map(encode_part,range(8)))
 concat=WORK/'concat.txt';concat.write_text('\n'.join("file '"+f+"'" for f in files)+'\n')
 chapter=[(0,117,'Round 1 — The Opening Six'),(117,233,'Round 2 — Movie Memories'),(233,349,'Round 3 — Changing Roles'),(349,465,'Round 4 — The Final Six'),(465,470,'Your score'),(470,480,'Credits')]
 meta=[';FFMETADATA1','title=24 Hollywood Actresses Then & Now — Enhanced Motion Edition','artist=The Screen Archive — independent editorial quiz','comment=24 actresses, 48 dated archival photographs, original role commentary. AI English narration. Music: Dream Culture, Kevin MacLeod, CC BY 4.0. Sources: Actresses_Credits.md.','copyright=Visual adaptation CC BY-SA 4.0. Original photographs retain their listed licenses.']
 for a,b,title in chapter:meta += ['[CHAPTER]','TIMEBASE=1/1000',f'START={a*1000}',f'END={b*1000}','title='+title]
 metap=WORK/'chapters.ffmetadata';metap.write_text('\n'.join(meta)+'\n')
 temp=WORK/'final_mux.mp4';target=OUT/'Hollywood_Actresses_8min_Enhanced.mp4'
 cmd=[FF,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(CACHE/'master.wav'),'-i',str(metap),'-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-af','loudnorm=I=-15.8:TP=-3.8:LRA=8','-metadata:s:a:0','language=eng','-t','480','-movflags','+faststart',str(temp)]
 subprocess.run(cmd,check=True);temp.replace(target)
 print(f'EPISODE_VIDEO_COMPLETE {target} ({target.stat().st_size/1e6:.2f} MB)',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--render',action='store_true');p.add_argument('--workers',type=int,default=2);a=p.parse_args()
 if a.preview:preview()
 if a.render:render(a.workers)

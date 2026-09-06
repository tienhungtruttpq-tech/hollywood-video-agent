from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'render_episode.py').read_text()
s=s.replace("CACHE=Path('/home/user/.cache/hollywood_actresses');PREP=CACHE/'prepared';WORK=CACHE/'render'", "CACHE=Path('/home/user/.cache/hollywood_actresses_refresh');PREP=Path('/home/user/.cache/hollywood_actresses/prepared');WORK=CACHE/'render'")
s=s.replace("ROOT/'timing.json'","ROOT/'timing_enhanced.json'")
s=s.replace("FONTS={};cv2.setNumThreads(1)","FONTS={};cv2.setNumThreads(1)\nOUTFIT=ROOT/'assets/fonts/Outfit.ttf'")
a=s.index("def font(size,face='sans',weight=500):");b=s.index('\ndef track(',a)
s=s[:a]+'''def font(size,face='sans',weight=600):
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
'''+s[b:]
# The animated strip is deliberately confined below the photos and attribution.
marker="PHOTOS={};SQUARE={};BASES={};PLACEHOLDER=None;CAPTIONS={};CREDIT_PAGES={};ROUND_PAGES={}"
insert=marker+'''
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
'''
assert marker in s;s=s.replace(marker,insert)
# Retain the approved photo framing and all source/caption data.
s=s.replace("a=ACTORS[i];p=APART[i];im=BACKGROUND.copy();d=ImageDraw.Draw(im)","a=ACTORS[i];p=APART[i];im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)")
s=s.replace("  text(d,(640,55),title,52,CREAM,'display',anchor='mt')","  # The larger Outfit headline is composited/animated in card().")
s=s.replace("text(d,(640,294),str(a['delta']),54", "text(d,(640,295),str(a['delta']),46")
s=s.replace("'THREE-SECOND CHALLENGE' if i==0 else 'ROLE CLUE'", "'FIRST GUESS / 3 SECONDS' if i==0 else 'ROLE CLUE'")
s=s.replace("p=APART[i];guess=cold_open or (i>0 and local<3.)\n im=layout(i,guess);im.paste(photo(i,'then'),(PX[0],PY))", "p=APART[i];guess=cold_open or (i>0 and local<3.)\n im=animated_background(t);overlay=layout(i,guess);im.paste(overlay,(0,0),overlay);im.paste(photo(i,'then'),(PX[0],PY))")
s=s.replace("text(d,(640,322),str(remaining),61", "text(d,(640,320),str(remaining),57")
# Caption card: bolder type over a translucent, dark, rounded panel.
a=s.index('def caption(text_value):');b=s.index('\ndef reveal(',a)
s=s[:a]+'''def caption(text_value):
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
'''+s[b:]
s=s.replace("im.paste(layer,(0,635),layer)","im.paste(layer,(0,625),layer)")
s=s.replace("im.paste(layer,(0,641),layer)","im.paste(layer,(0,625),layer)")
s=s.replace("im.paste(layer,(0,632),layer)","im.paste(layer,(0,625),layer)")
needle=" return im\n\ndef photo_montage(ids):"
assert needle in s;s=s.replace(needle," im=headline(im,i,guess,local)\n return im\n\ndef photo_montage(ids):")
s=s.replace("im=ROUND_PAGES[n].copy();d=ImageDraw.Draw(im)","im=with_flow(ROUND_PAGES[n].copy(),p['start']+local);d=ImageDraw.Draw(im)")
s=s.replace("f'ROUND {n+1}',108", "f'ROUND {n+1}',88")
s=s.replace("im=photo_montage([0,1,4,18,22,23]);d=ImageDraw.Draw(im)","im=with_flow(photo_montage([0,1,4,18,22,23]),t);d=ImageDraw.Draw(im)")
s=s.replace("'YOUR SCORE / 24?',107", "'YOUR SCORE / 24?',79")
# Credits become a transparent text layer so the lower background keeps moving.
s=s.replace("im=BACKGROUND.copy();d=ImageDraw.Draw(im)\n track(d,(58,28),'THE SCREEN ARCHIVE / SOURCES & CREDITS'", "im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)\n track(d,(58,28),'THE SCREEN ARCHIVE / SOURCES & CREDITS'")
s=s.replace("'REAL PHOTOS. ORIGINAL QUIZ.',66", "'REAL PHOTOS. ORIGINAL QUIZ.',52")
s=s.replace("'THE PHOTOGRAPHERS & ARCHIVES',51", "'THE PHOTOGRAPHERS & ARCHIVES',44")
# New cold open: three quick, real archival portraits, then a full 3-second guess.
point='def frame(t):'
a=s.index(point)
intro='''def opening_montage(t):
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

'''
s=s[:a]+intro+s[a:]
s=s.replace(" if t<3:im=card(0,t,t,True)\n elif t>=470:im=credits(0 if t<475 else 1)", " if t<2:im=opening_montage(t)\n elif t<5:im=card(0,t-2,t,True)\n elif t>=470:\n  overlay=credits(0 if t<475 else 1);im=animated_background(t);im.paste(overlay,(0,0),overlay)")
s=s.replace("for t in [.5,2.7,3.2,25.,116.,117.5,465.8,472.]:", "for t in [.35,1.05,1.65,2.5,4.7,5.2,5.8,10.,10.7,25.8,117.5,465.8,472.]:")
s=s.replace("'render_episode.py','actors.json','framing.json','timing.json'", "'render_enhanced.py','actors.json','framing.json','timing_enhanced.json'")
s=s.replace("'Hollywood_Actresses_Then_Now_Quiz_8min.mp4'", "'Hollywood_Actresses_8min_Enhanced.mp4'")
s=s.replace("'24 Hollywood Actresses Then & Now — The 3-Second Quiz'", "'24 Hollywood Actresses Then & Now — Enhanced Motion Edition'")
# Main title is embedded as FFmetadata text, not a Python string on its own.
s=s.replace('title=24 Hollywood Actresses Then & Now — The 3-Second Quiz','title=24 Hollywood Actresses Then & Now — Enhanced Motion Edition')
s=s.replace("'-crf','24'","'-crf','25'")
(ROOT/'render_enhanced.py').write_text(s)
print('Enhanced renderer created: Outfit headlines, animated lower backdrop, refreshed opening.')

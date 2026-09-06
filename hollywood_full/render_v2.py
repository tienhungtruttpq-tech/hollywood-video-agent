#!/usr/bin/env python3
"""Render a new eight-minute, 30-actor archival-photo comparison.
No image generation, face morphing, face replacement or AI aging is used.
"""
from pathlib import Path
import os,sys,json,math,re,html,bisect,argparse,subprocess,concurrent.futures,hashlib
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont,ImageOps
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_full');PREP=CACHE/'prepared';RENDER=CACHE/'render_v2'
OUT=ROOT/'output';RENDER.mkdir(parents=True,exist_ok=True);OUT.mkdir(exist_ok=True)
W,H,FPS,DURATION=1280,720,30,480.
BG=(16,16,24);CREAM=(245,242,237);LAV=(184,171,248);MUTED=(150,146,164);LINE=(57,53,73)
ACTORS=json.loads((ROOT/'actors.json').read_text())
TIMING=json.loads((ROOT/'timing.json').read_text())
PARTS={p['id']:p for p in TIMING['parts']}
NARR=json.loads((ROOT/'narrative.json').read_text());CHAPTERS=NARR['chapters']
FF=imageio_ffmpeg.get_ffmpeg_exe();cv2.setNumThreads(1)
DISPLAY=str(ROOT/'assets/fonts/BebasNeue-Regular.ttf');SANS=str(ROOT/'assets/fonts/Manrope.ttf')
FONTS={}
def font(size,face='sans',weight=500):
    key=(size,face,weight)
    if key not in FONTS:
        f=ImageFont.truetype(DISPLAY if face=='display' else SANS,int(size))
        if face=='sans':
            try:f.set_variation_by_axes([weight])
            except Exception:pass
        FONTS[key]=f
    return FONTS[key]
def txt(d,xy,text,size=18,color=CREAM,face='sans',weight=500,anchor=None):
    d.text(xy,text,font=font(size,face,weight),fill=color,anchor=anchor)
def track(d,xy,text,size=10,space=1.5,color=MUTED,anchor='left'):
    f=font(size,weight=600);width=sum(d.textlength(c,font=f) for c in text)+space*max(0,len(text)-1)
    x,y=xy
    if anchor=='center':x-=width/2
    if anchor=='right':x-=width
    for c in text:d.text((x,y),c,font=f,fill=color);x+=d.textlength(c,font=f)+space
    return width
def ease(t):
    t=max(0.,min(1.,float(t)));return t*t*(3-2*t)
def wrap(text,width,size):
    f=font(size);lines=[];current=''
    for word in text.split():
        candidate=(current+' '+word).strip()
        if f.getlength(candidate)>width and current:lines.append(current);current=word
        else:current=candidate
    if current:lines.append(current)
    return lines

y,x=np.mgrid[0:H,0:W]
r=((x-W*.50)/(W*.9))**2+((y-H*.25)/(H*1.0))**2
noise=np.random.default_rng(23).normal(0,.38,(H,W))
bg=np.zeros((H,W,3),np.float32)
for c,base in enumerate(BG):bg[:,:,c]=base+np.clip(1-r,0,1)*(3 if c<2 else 7)+noise
BGIMG=Image.fromarray(np.clip(bg,0,255).astype('uint8'));del bg,x,y,r,noise
PHOTO={};LAYOUT={};CREDIT={};CAPTION={};HOLD={};HERO={};ENDING={}

def source_photo(i,era):
    k=(i,era)
    if k not in PHOTO:PHOTO[k]=np.asarray(Image.open(PREP/f'{i:02d}_{era}.jpg').convert('RGB'))
    return PHOTO[k]

def motion(i,era,size,q):
    a=source_photo(i,era);w,h=size;q=ease(q);mode=(i+(era=='now'))%4
    native=ACTORS[i][era]['downloaded_size'];amount=.012 if min(native)<450 else .032
    if mode==0:z=1+amount*q
    elif mode==1:z=1+amount*(1-q)
    elif mode==2:z=1+amount
    else:z=1+amount*(.3+.7*q)
    cover=max(w/a.shape[1],h/a.shape[0]);sx=1/(cover*z);sy=sx
    gapx=a.shape[1]-sx*w;gapy=a.shape[0]-sy*h
    cx=.5+(q-.5)*.42 if mode==2 else .5+(q-.5)*.12
    cy=.30+(q-.5)*.20
    M=np.array([[sx,0,gapx*cx],[0,sy,gapy*cy]],np.float32)
    return cv2.warpAffine(a,M,(w,h),flags=cv2.INTER_CUBIC|cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REPLICATE)

def plain(s):
    s=html.unescape(html.unescape(s));s=re.sub('<[^>]+>','',s);return re.sub(r'\s+',' ',s).strip()
def author_short(p,i=None,era=None):
    if i==2 and era=='now':return 'Benjamin Applebaum / DoD'
    if i==21 and era=='then':return 'Public-domain White House archive'
    s=plain(p['artist'])
    s=re.sub(r'\s+from\s+(Peoria|Surprise|United States|Los Angeles).*','',s)
    s=s.replace('Jaud (de:Benutzer:Falkenauge)','Jaud (Falkenauge)')
    s=s.replace('Chairman of the Joint Chiefs of Staff','US Joint Chiefs of Staff')
    if len(s)>61:s=s[:58].rstrip()+'…'
    return s

def credit_layer(i,era):
    k=(i,era)
    if k not in CREDIT:
        ol=Image.new('RGBA',(484,480));d=ImageDraw.Draw(ol)
        for yy in range(419,480):d.line((0,yy,484,yy),fill=(7,7,13,int(205*((yy-419)/61)**1.2)))
        p=ACTORS[i][era];label=author_short(p,i,era)+'  /  '+p['license']
        size=10
        if font(size).getlength(label)>456:size=9
        txt(d,(12,454),label,size,(235,229,240),weight=500)
        CREDIT[k]=ol
    return CREDIT[k]

def with_credit(arr,i,era):
    return Image.alpha_composite(Image.fromarray(arr).convert('RGBA'),credit_layer(i,era)).convert('RGB')

PLACEHOLDERS={};HOLD_BLANK={}
def hold_image(i):
    if i not in PLACEHOLDERS:
        ar=np.zeros((480,484,3),np.uint8);yy,xx=np.mgrid[0:480,0:484]
        g=np.exp(-(((xx-242)/340)**2+((yy-232)/370)**2)*2.5)
        for k,c in enumerate([27,24,39]):ar[:,:,k]=c+g*[10,8,17][k]
        im=Image.fromarray(ar);d=ImageDraw.Draw(im)
        for xx in range(-480,500,37):d.line((xx,0,xx+480,480),fill=(44,38,60),width=1)
        HOLD_BLANK[i]=np.asarray(im.copy())
        track(d,(242,176),'FAST FORWARD',12,2.6,LAV,'center')
        txt(d,(242,207),'+'+str(ACTORS[i]['delta']),82,CREAM,'display',anchor='mt')
        track(d,(242,311),'YEARS LATER',11,2.4,MUTED,'center')
        PLACEHOLDERS[i]=np.asarray(im)
    return PLACEHOLDERS[i]

def reveal(i,photo,q):
    if q<=0:return Image.fromarray(hold_image(i))
    if q>=1:return photo
    p=ease(q);a=np.asarray(photo);b=hold_image(i)
    fade=ease(q/.25);b=(b*(1-fade)+HOLD_BLANK[i]*fade).astype(np.uint8)
    mode=[5,0,4,1,3,2][i%6]
    if mode==0:
        edge=(484+30)*p-15;mask=np.clip((edge-np.arange(484))/17,0,1)[None,:,None]
    elif mode==1:
        edge=(480+30)*(1-p)-15;mask=np.clip((np.arange(480)-edge)/17,0,1)[:,None,None]
    elif mode==2:
        dist=np.abs(np.arange(484)-242);edge=258*p-8;mask=np.clip((edge-dist)/16,0,1)[None,:,None]
    elif mode==3:
        off=round(484*(1-p));result=b.copy()
        if off<484:result[:,off:]=a[:,:484-off]
        if 0<off<484:result[:,max(0,off-2):off]=np.array(LAV,dtype=np.uint8)
        return Image.fromarray(result)
    elif mode==4:
        # Feathered diagonal wipe: only opacity changes, not facial geometry.
        yy,xx=np.mgrid[0:480,0:484]
        plane=(xx/484+.75*yy/480)/1.75
        mask=np.clip((1.12*p-.04-plane)/.055,0,1)[:,:,None]
    else:
        # A circular iris begins near the portrait's eye line and opens out.
        yy,xx=np.mgrid[0:480,0:484]
        radius=np.sqrt((xx-242)**2+(yy-220)**2)
        mask=np.clip((400*p-20-radius)/18,0,1)[:,:,None]
    return Image.fromarray((a*mask+b*(1-mask)).astype(np.uint8))

def actor_layout(i):
    if i not in LAYOUT:
        a=ACTORS[i];im=BGIMG.copy();d=ImageDraw.Draw(im)
        track(d,(72,20),'THE SCREEN ARCHIVE',10,2.5)
        track(d,(1208,20),f'{i//5+1:02d} / '+CHAPTERS[i//5],10,1.35,anchor='right')
        txt(d,(72,48),'THEN',44,LAV,'display')
        txt(d,(556,59),str(a['years'][0]),25,CREAM,weight=650,anchor='ra')
        txt(d,(724,48),'NOW',44,LAV,'display')
        txt(d,(1208,59),str(a['years'][1]),25,CREAM,weight=650,anchor='ra')
        track(d,(640,65),f'{i+1:02d} / 30',11,1.2,anchor='center')
        txt(d,(640,280),str(a['delta']),69,LAV,'display',anchor='mt')
        track(d,(640,365),'YEARS',10,2.0,MUTED,'center')
        track(d,(640,384),'APART',10,2.0,MUTED,'center')
        d.line((602,426,678,426),fill=LINE,width=1)
        d.line((672,421,678,426,672,431),fill=(130,119,172),width=1)
        size=48
        while font(size,'display').getlength(a['name'].upper())>560:size-=1
        txt(d,(72,608),a['name'].upper(),size,CREAM,'display')
        links=' / '.join(PARTS[f'actor_{i:02d}']['films'])
        if font(11).getlength(links)>555:
            links=' / '.join(PARTS[f'actor_{i:02d}']['films'][:2])
        txt(d,(73,662),links,11,MUTED)
        track(d,(72,696),'PHOTO YEARS SHOWN / "NOW" = LATER DATED IMAGE / NO AI FACE ALTERATIONS',9,.8,(118,114,134))
        LAYOUT[i]=im
    return LAYOUT[i].copy()

def caption_image(text):
    if text not in CAPTION:
        sz=18;lines=wrap(text,528,sz)
        while len(lines)>3 and sz>15:sz-=1;lines=wrap(text,528,sz)
        layer=Image.new('RGBA',(546,88));d=ImageDraw.Draw(layer)
        for j,line in enumerate(lines):txt(d,(0,j*(sz+7)),line,sz,CREAM)
        CAPTION[text]=layer
    return CAPTION[text]

def actor_frame(i,local):
    part=PARTS[f'actor_{i:02d}'];t=part['start']+local;im=actor_layout(i)
    then=motion(i,'then',(484,480),local/15)
    now=motion(i,'now',(484,480),max(0,local-part['reveal'])/(15-part['reveal']))
    left=with_credit(then,i,'then');right=with_credit(now,i,'now')
    phase=(local-part['reveal'])/.98
    right=reveal(i,right,phase)
    im.paste(left,(72,108));im.paste(right,(724,108))
    d=ImageDraw.Draw(im)
    d.rectangle((71,107,556,588),outline=LINE,width=1);d.rectangle((723,107,1208,588),outline=LINE,width=1)
    if 0<phase<1:
        # A screen-locked border highlight emphasizes the new photograph.
        glow=math.sin(math.pi*phase)
        edge=tuple(round(LINE[c]*(1-glow)+LAV[c]*glow) for c in range(3))
        d.rectangle((723,107,1208,588),outline=edge,width=2)
    # Thin timeline sweep is descriptive motion, not a fabricated intermediate year.
    q=ease(local/15);end=602+76*q
    d.line((602,426,end,426),fill=LAV,width=1)
    d.ellipse((end-2,424,end+2,428),fill=LAV)
    for c in part['captions']:
        if c['start']<=t<c['end']:
            layer=caption_image(c['text']);im.paste(layer,(680,612),layer);break
    return im

def hero_frame(local,outro=False):
    if outro:
        groups=[[7,11,23],[7,11,23],[7,11,23]];group=0
    else:
        groups=[[0,1,2],[6,7,20],[4,11,25]];group=min(2,int(local/3.35))
    ids=groups[group];im=Image.new('RGB',(W,H));x=0
    for j,(ai,w) in enumerate(zip(ids,[427,426,427])):
        ar=motion(ai,'now',(w,720),local/10)
        im.paste(Image.fromarray(ar),(x,0));x+=w
    ar=np.asarray(im).astype(np.float32);gy=np.arange(H)[:,None,None]
    shade=.17+.80*np.clip((gy-115)/570,0,1)**1.35
    if outro:shade=np.maximum(shade,.29)
    ar*=1-shade;ar+=np.array(BG)[None,None,:]*shade
    im=Image.fromarray(np.clip(ar,0,255).astype('uint8'));d=ImageDraw.Draw(im)
    d.line((426,0,426,H),fill=(38,34,45),width=2);d.line((853,0,853,H),fill=(38,34,45),width=2)
    track(d,(54,30),'THE SCREEN ARCHIVE',11,2.5,CREAM)
    track(d,(W-54,30),'HOLLYWOOD / THEN & NOW',11,1.4,CREAM,'right')
    for ai,cx in zip(ids,[213,640,1066]):
        track(d,(cx,80),ACTORS[ai]['name'].upper()+' / '+str(ACTORS[ai]['years'][1]),10,1.0,CREAM,'center')
    if not outro:
        track(d,(640,378),'HOLLYWOOD',17,6.5,LAV,'center')
        txt(d,(640,412),'THEN & NOW',152,CREAM,'display',anchor='mt')
        track(d,(640,596),'30 STARS / 60 PHOTOGRAPHS',16,2.0,LAV,'center')
        # The synchronized introduction caption occupies this footer.
    else:
        track(d,(640,414),'THIRTY CAREERS. COUNTLESS MOVIE MEMORIES.',12,1.9,LAV,'center')
        txt(d,(640,449),'WHO SHOULD BE NEXT?',99,CREAM,'display',anchor='mt')
        txt(d,(640,580),'Which comparison surprised you most?',21,CREAM,anchor='mt')
        # The synchronized ending caption occupies this footer.
    part=PARTS['outro' if outro else 'intro']
    absolute=local+(460 if outro else 0)
    for cue in part['captions']:
        if cue['start']<=absolute<cue['end']:
            for line_index,line in enumerate(wrap(cue['text'],1100,18)):
                txt(d,(640,650+line_index*25),line,18,CREAM,anchor='mt')
            break
    return im

def credits_frame(page):
    if page in ENDING:return ENDING[page].copy()
    im=BGIMG.copy();d=ImageDraw.Draw(im)
    track(d,(64,32),'THE SCREEN ARCHIVE / CREDITS',11,2.5)
    if page==0:
        txt(d,(64,78),'THE SOUND OF THE JOURNEY',60,CREAM,'display')
        track(d,(64,192),'MUSIC',12,2.6,LAV)
        txt(d,(64,229),'Dream Culture',46,CREAM,'display')
        txt(d,(64,292),'Kevin MacLeod  /  incompetech.com',25,CREAM,weight=600)
        txt(d,(64,340),'Licensed under Creative Commons: By Attribution 4.0',19,MUTED)
        txt(d,(64,376),'creativecommons.org/licenses/by/4.0/',18,LAV)
        d.line((64,435,1216,435),fill=LINE,width=1)
        txt(d,(64,466),'English narration generated with the selected AI voice.',19,CREAM)
        txt(d,(64,508),'Original edit, motion graphics, transitions and sound accents.',19,CREAM)
        txt(d,(64,550),'30 actors. 60 dated archival photographs. No AI aging or face replacement.',17,MUTED)
        track(d,(64,662),'PHOTO ATTRIBUTIONS FOLLOW / FULL SOURCES IN THE COMPANION CREDITS FILE',10,1.3,MUTED)
    else:
        txt(d,(64,72),'REAL PHOTOS. DATED SOURCES.',53,CREAM,'display')
        txt(d,(64,144),'THEN author / LATER author  ·  Individual photo licenses appear in the video.',14,MUTED)
        for col in range(2):
            for row in range(15):
                i=col*15+row;a=ACTORS[i];xx=64+col*602;yy=190+row*25
                name=a['name']
                credits=author_short(a['then'],i,'then')+' / '+author_short(a['now'],i,'now')
                label=f'{i+1:02d}  {name}:  {credits}'
                sz=10
                while font(sz).getlength(label)>548 and sz>8:sz-=1
                if font(sz).getlength(label)>548:
                    while font(sz).getlength(label+'…')>548:label=label[:-1]
                    label+='…'
                txt(d,(xx,yy),label,sz,CREAM)
        d.line((64,591,1216,591),fill=LINE,width=1)
        txt(d,(64,608),'Full photo links, licenses and reuse notes: Hollywood_Credits_8min.md',17,CREAM)
        txt(d,(64,646),'Visual adaptation: CC BY-SA 4.0  ·  creativecommons.org/licenses/by-sa/4.0/',14,MUTED)
        track(d,(64,686),'INDEPENDENT EDIT / NO ENDORSEMENT BY THE FEATURED PEOPLE IS IMPLIED',9,1.3,MUTED)
    ENDING[page]=im.copy();return im

def scene_at(t):
    if t<10:return 'intro',0,t
    if t<460:
        i=min(29,int((t-10)//15));return 'actor',i,t-(10+i*15)
    if t<470:return 'outro',0,t-460
    return 'credits',min(1,int((t-470)//5)),(t-470)%5

def raw_frame(t):
    kind,i,local=scene_at(t)
    if kind=='actor':return actor_frame(i,local)
    if kind=='intro':return hero_frame(local)
    if kind=='outro':return hero_frame(local,True)
    return credits_frame(i)

def frame(t):
    kind,i,local=scene_at(t);im=raw_frame(t)
    start=t-local
    if start>0 and local<.30:
        k=(kind,i)
        if k not in HOLD:HOLD[k]=raw_frame(start-1/FPS)
        im=Image.blend(HOLD[k],im,ease(local/.30))
    # A single travelling film-strip gate marks each new five-actor chapter.
    if kind=='actor' and i%5==0 and local<.68:
        x=round(-255+(W+520)*ease(local/.68));d=ImageDraw.Draw(im)
        d.rectangle((x,0,x+208,H),fill=(28,24,41))
        for yy in range(10,H,35):
            d.rounded_rectangle((x+8,yy,x+20,yy+20),radius=2,fill=(151,140,194))
            d.rounded_rectangle((x+188,yy,x+200,yy+20),radius=2,fill=(151,140,194))
        txt(d,(x+104,280),f'{i//5+1:02d}',87,LAV,'display',anchor='mt')
        track(d,(x+104,387),'CHAPTER',10,2,LAV,'center')
    if kind=='actor' and i%5==0 and .18<local<1.18:
        # A restrained warm light-leak sweep, not a white flash or strobe.
        u=(local-.18);xx=np.arange(W,dtype=np.float32)[None,:]
        yy=np.arange(H,dtype=np.float32)[:,None]
        centre=-230+(W+460)*ease(u)
        band=np.exp(-((xx-centre-.16*(yy-H*.5))/118)**2)
        alpha=(band*.14*math.sin(math.pi*u))[:,:,None]
        ar=np.asarray(im,dtype=np.float32)
        ar=ar*(1-alpha)+np.array([249,214,173],np.float32)[None,None,:]*alpha
        im=Image.fromarray(np.clip(ar,0,255).astype(np.uint8))
    if t>DURATION-.55:im=Image.blend(im,Image.new('RGB',(W,H),BG),ease((t-DURATION+.55)/.55))
    d=ImageDraw.Draw(im);d.rectangle((0,716,W,719),fill=(39,35,52));d.rectangle((0,716,int(W*t/DURATION),719),fill=LAV)
    for chapter in range(6):
        xx=round((10+chapter*75)/DURATION*W);d.rectangle((xx,716,xx+2,719),fill=(106,96,142))
    return im

def preview():
    for page in range(3):
        canvas=Image.new('RGB',(1280,1800),BG)
        for j,i in enumerate(range(page*10,page*10+10)):
            im=frame(10+i*15+9.5)
            im.resize((640,360),Image.Resampling.LANCZOS).save(RENDER/f'qc_actor_{i:02d}.jpg',quality=92)
            canvas.paste(im.resize((640,360),Image.Resampling.LANCZOS),((j%2)*640,(j//2)*360))
        canvas.save(ROOT/'work'/f'v2_layout_{page+1}.jpg',quality=92)
    frame(.7).save(OUT/'Hollywood_8min_V2_Poster.jpg',quality=95)
    examples=[(10+3.9,'wipe'),(25+4.8,'vertical'),(40+4.8,'shutter'),(55+4.8,'slide'),(85+.34,'chapter'),(472,'music-credit')]
    for t,name in examples:frame(t).save(RENDER/f'effect_{name}.jpg',quality=92)
    print('PREVIEWS_READY',flush=True)

def encode_segment(index):
    start=index*60;end=min(DURATION,start+60);dest=RENDER/f'segment_{index:02d}.mp4'
    if dest.exists() and dest.stat().st_size>50000:return str(dest)
    cmd=[FF,'-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24',
         '-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','23',
         '-pix_fmt','yuv420p','-threads','2','-g','60','-keyint_min','30','-movflags','+faststart',str(dest)]
    with open(RENDER/f'encode_{index:02d}.log','w') as log:
        p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        try:
            for n in range(round(start*FPS),round(end*FPS)):
                p.stdin.write(frame(n/FPS).tobytes())
            p.stdin.close();code=p.wait()
        except BaseException:p.kill();dest.unlink(missing_ok=True);raise
    if code:
        dest.unlink(missing_ok=True);raise RuntimeError((RENDER/f'encode_{index:02d}.log').read_text())
    print(f'VIDEO_PART_COMPLETE {index+1}/8 ({dest.stat().st_size/1e6:.1f} MB)',flush=True)
    return str(dest)

def metadata():
    lines=[';FFMETADATA1','title=Hollywood Then & Now — 30 Stars | 8-Minute Edition V2 — Enhanced Music & Transitions',
           'artist=The Screen Archive — independent archival-photo edit',
           'comment=60 dated archival photos; no AI face aging. AI English narration. Music: Dream Culture, Kevin MacLeod (incompetech.com), CC BY 4.0. Full sources accompany this file in Hollywood_Credits_8min.md.',
           'copyright=Visual adaptation CC BY-SA 4.0. Source photographs and music retain their listed credits and licenses.']
    entries=[(0,10,'Introduction: 30 Stars / 60 Photographs')]
    entries += [(10+i*15,25+i*15,a['name']+f' | {a["years"][0]} / {a["years"][1]}') for i,a in enumerate(ACTORS)]
    entries += [(460,470,'Which star should be next?'),(470,475,'Music credits'),(475,480,'Photo credits')]
    for start,end,title in entries:lines += ['[CHAPTER]','TIMEBASE=1/1000',f'START={round(start*1000)}',f'END={round(end*1000)}','title='+title]
    path=RENDER/'chapters.ffmetadata';path.write_text('\n'.join(lines)+'\n');return path

def render(workers=2):
    digest=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in ['render_v2.py','actors.json','framing.json','timing.json'])).hexdigest()
    stamp=RENDER/'config_hash.txt'
    if not stamp.exists() or stamp.read_text()!=digest:
        for old in RENDER.glob('segment_*.mp4'):old.unlink()
        stamp.write_text(digest)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        files=list(pool.map(encode_segment,range(8)))
    listing=RENDER/'concat.txt';listing.write_text('\n'.join("file '"+f.replace("'","'\\''")+"'" for f in files)+'\n')
    output=OUT/'Hollywood_Then_Now_8min_V2.mp4';meta=metadata();mix=CACHE/'master_mix_v2.wav'
    if not mix.exists():raise FileNotFoundError('Prepare the full music/voice mix with mix_audio_v2.py first.')
    command=[FF,'-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(listing),
             '-i',str(mix),'-i',str(meta),'-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2',
             '-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-af','loudnorm=I=-15.5:TP=-1.8:LRA=8',
             '-metadata:s:a:0','language=eng','-t','480','-movflags','+faststart',str(output)]
    subprocess.run(command,check=True)
    print(f'VIDEO_COMPLETE {output} ({output.stat().st_size/1e6:.1f} MB)',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');ap.add_argument('--render',action='store_true');ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    if not PREP.exists() or not (PREP/'29_now.jpg').exists():
        from prepare_photos import prepare
        prepare()
    if args.preview:preview()
    if args.render:render(args.workers)

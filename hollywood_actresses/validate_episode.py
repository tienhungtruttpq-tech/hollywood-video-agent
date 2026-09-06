from pathlib import Path
import json,re,subprocess,hashlib
import cv2,imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent;CACHE=Path('/home/user/.cache/hollywood_actresses')
FILE=ROOT/'output/Hollywood_Actresses_Then_Now_Quiz_8min.mp4';FF=imageio_ffmpeg.get_ffmpeg_exe()
c=cv2.VideoCapture(str(FILE));assert c.isOpened()
w=int(c.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(c.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=c.get(cv2.CAP_PROP_FPS);frames=int(c.get(cv2.CAP_PROP_FRAME_COUNT));duration=frames/fps
assert (w,h)==(1280,720),(w,h);assert abs(fps-24)<1e-6;assert frames==11520,frames;assert abs(duration-480)<.001
actors=json.loads((ROOT/'actors.json').read_text());timing=json.loads((ROOT/'timing.json').read_text())['parts']
assert len(actors)==24 and len({p['source'] for a in actors for p in [a['then'],a['now']]})==48
for p in timing:
 assert p['audio_start']>=p['start']+p.get('guess',0)
 assert p['audio_start']+p['audio_duration']<=p['start']+p['duration']+.015,(p['id'],p['audio_duration'])
# Full decode plus broadcast-style loudness measurement on the actual MP4.
p=subprocess.run([FF,'-hide_banner','-nostats','-i',str(FILE),'-filter_complex','[0:a:0]ebur128=peak=true[a]','-map','0:v:0','-map','[a]','-f','null','-'],capture_output=True,text=True,timeout=240)
assert p.returncode==0,p.stderr[-1000:]
s=p.stderr[p.stderr.rfind('Summary:'):];(ROOT/'work/loudness.txt').write_text(s)
I=re.search(r'I:\s*(-?[\d.]+) LUFS',s);TP=re.search(r'Peak:\s*(-?[\d.]+) dBFS',s);LRA=re.search(r'LRA:\s*([\d.]+) LU',s)
# Subtitle times are ordered, non-overlapping and contained by the program.
srt=(ROOT/'output/Actresses_Then_Now_EN.srt').read_text()
def sec(x):
 h,m,s=x.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
ranges=[[sec(a),sec(b)] for a,b in re.findall(r'(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)',srt)]
for a,b in ranges:assert 0<=a<b<=480,(a,b)
for a,b in zip(ranges,ranges[1:]):assert a[1]<=b[0]+.001,(a,b)
# Review the published encoding at quiz/reveal/round-change/credit moments.
times=[0.5,2.8,3.1,3.8,15.0,22.5,25.1,25.8,60.5,63.8,117.4,163.,252.,289.,352.,451.,466.,473.,477.]
font=ImageFont.truetype('/home/user/hollywood_full/assets/fonts/Manrope.ttf',14)
for page in range(3):
 group=times[page*7:page*7+7];sheet=Image.new('RGB',(1280,388*((len(group)+1)//2)),(16,17,25));d=ImageDraw.Draw(sheet)
 for j,t in enumerate(group):
  c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,bgr=c.read();assert ok,t
  im=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)).resize((640,360),Image.Resampling.LANCZOS);x=j%2*640;y=j//2*388;sheet.paste(im,(x,y));d.text((x+8,y+363),f'ACTUAL MP4 / {t:.2f}s',font=font,fill=(206,186,248))
 sheet.save(CACHE/'render'/f'encoded_review_{page+1}.jpg',quality=94)
c.release()
for name in ['Thumbnail_A_Then_Now.jpg','Thumbnail_B_Quiz.jpg']:
 assert Image.open(ROOT/'output'/name).size==(1280,720)
result={'file':FILE.name,'width':w,'height':h,'fps':fps,'frames':frames,'duration_seconds':duration,'bytes':FILE.stat().st_size,'full_decode_exit':p.returncode,'actresses':24,'unique_photographs':48,'subtitle_cues':len(ranges),'first_name_reveal_seconds':3.0,'second_name_reveal_seconds':25.0,'audio_integrated_lufs':float(I.group(1)) if I else None,'audio_true_peak_dbfs':float(TP.group(1)) if TP else None,'audio_lra_lu':float(LRA.group(1)) if LRA else None,'sha256':hashlib.sha256(FILE.read_bytes()).hexdigest()}
(ROOT/'work/validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));print(s)

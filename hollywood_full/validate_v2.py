from pathlib import Path
import cv2,subprocess,json,re,hashlib
import imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
VIDEO=ROOT/'output/Hollywood_Then_Now_8min_V2.mp4'
FF=imageio_ffmpeg.get_ffmpeg_exe()
c=cv2.VideoCapture(str(VIDEO));assert c.isOpened()
w=int(c.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(c.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=c.get(cv2.CAP_PROP_FPS);frames=int(c.get(cv2.CAP_PROP_FRAME_COUNT));duration=frames/fps
assert (w,h)==(1280,720),(w,h)
assert abs(fps-30)<1e-5,fps
assert frames==14400,frames
assert abs(duration-480)<.001,duration
# Inspect the encoded file, not only the source renderer.
timing=json.loads((ROOT/'timing.json').read_text());parts={p['id']:p for p in timing['parts']}
times=[.8]+[parts[f'actor_{i:02d}']['start']+parts[f'actor_{i:02d}']['reveal']+.49 for i in range(6)]+[85.65,169.8,179.5,249.5,294.5,344.5,374.5,404.5,449.5,462.3,472.,477.]
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
for page in range(3):
 subset=times[page*7:(page+1)*7]
 canvas=Image.new('RGB',(1280,388*((len(subset)+1)//2)),(17,16,24));d=ImageDraw.Draw(canvas)
 for j,t in enumerate(subset):
  c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=c.read();assert ok,t
  rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB);im=Image.fromarray(rgb);im=im.resize((640,360),Image.Resampling.LANCZOS)
  x=(j%2)*640;y=(j//2)*388;canvas.paste(im,(x,y));d.text((x+8,y+362),f'ENCODED MP4 / {t:.2f}s',font=font,fill=(202,192,247))
 canvas.save(ROOT/'work'/f'v2_encoded_review_{page+1}.jpg',quality=93)
c.release()
command=[FF,'-hide_banner','-nostats','-i',str(VIDEO),'-filter_complex','[0:a:0]ebur128=peak=true[a]','-map','0:v:0','-map','[a]','-f','null','-']
r=subprocess.run(command,capture_output=True,text=True,timeout=240)
assert r.returncode==0,r.stderr[-1500:]
summary=r.stderr[r.stderr.rfind('Summary:'):]
(ROOT/'work/audio_loudness_v2.txt').write_text(summary+'\n')
i=re.search(r'I:\s*(-?[\d.]+) LUFS',summary);pk=re.search(r'Peak:\s*(-?[\d.]+) dBFS',summary);lra=re.search(r'LRA:\s*([\d.]+) LU',summary)
# Confirm subtitle ordering and time bounds.
srt=(ROOT/'output/Hollywood_Then_Now_8min_EN.srt').read_text();ranges=[]
def seconds(s):
 a,b,c=s.replace(',','.').split(':');return int(a)*3600+int(b)*60+float(c)
for a,b in re.findall(r'(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)',srt):
 start,end=seconds(a),seconds(b);assert 0<=start<end<=480;(ranges.append([start,end]))
for a,b in zip(ranges,ranges[1:]):assert a[1]<=b[0]+.001,(a,b)
actors=json.loads((ROOT/'actors.json').read_text());assert len(actors)==30
assert len({p['source'] for a in actors for p in [a['then'],a['now']]})==60
result={'file':VIDEO.name,'width':w,'height':h,'fps':fps,'frames':frames,'duration_seconds':duration,'bytes':VIDEO.stat().st_size,'full_decode_exit':r.returncode,'subtitle_cues':len(ranges),'unique_actors':30,'unique_photo_sources':60,'audio_integrated_lufs':float(i.group(1)) if i else None,'audio_true_peak_dbfs':float(pk.group(1)) if pk else None,'audio_lra_lu':float(lra.group(1)) if lra else None,'sha256':hashlib.sha256(VIDEO.read_bytes()).hexdigest()}
(ROOT/'work/validation_v2.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));print(summary)

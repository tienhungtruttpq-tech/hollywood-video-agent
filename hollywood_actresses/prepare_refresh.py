from pathlib import Path
import json,copy,wave,subprocess,math
import numpy as np
from scipy.signal import butter,sosfilt
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_actresses_refresh');(CACHE/'audio').mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();SR=24000
HOOK='You know these faces. Can you name them?'

def read_audio(p,channels=1):
 r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(p),'-f','f32le','-ac',str(channels),'-ar',str(SR),'pipe:1'],capture_output=True,check=True)
 a=np.frombuffer(r.stdout,dtype='<f4').copy();return a if channels==1 else a.reshape(-1,channels)
def writewav(p,a):
 with wave.open(str(p),'wb') as w:
  w.setnchannels(1 if a.ndim==1 else a.shape[1]);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())
def stamp(t):
 n=round(t*1000);return f'{n//3600000:02d}:{n//60000%60:02d}:{n//1000%60:02d},{n%1000:03d}'

base=json.loads((ROOT/'timing.json').read_text());data=copy.deepcopy(base);parts=data['parts']
hook=read_audio(CACHE/'audio/hook.wav');nz=np.flatnonzero(np.abs(hook)>.003)
if len(nz):hook=hook[max(0,nz[0]-int(.08*SR)):min(len(hook),nz[-1]+int(.14*SR))]
if len(hook)/SR>4.65:
 writewav(CACHE/'audio/hook_trim.wav',hook);speed=len(hook)/SR/4.65
 subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(CACHE/'audio/hook_trim.wav'),'-af',f'atempo={speed}',str(CACHE/'audio/hook_fit.wav')],check=True);hook=read_audio(CACHE/'audio/hook_fit.wav')
active=hook[np.abs(hook)>.013];rms=float(np.sqrt(np.mean(active*active))) if len(active) else .1
gain=min(1.9,.15/max(rms,1e-6),.87/max(float(np.max(np.abs(hook))),1e-6));hook*=gain
writewav(CACHE/'audio/hook_final.wav',hook)
for p in parts:
 if p['id']=='intro':
  p.update(text=HOOK,caption=HOOK,start=0.,duration=5.,file=str(CACHE/'audio/hook_final.wav'),audio_start=.12,audio_duration=len(hook)/SR,source_duration=len(hook)/SR,speed=1.)
  p['captions']=[dict(start=.12,end=.12+len(hook)/SR,text=HOOK)]
 elif p['id']=='actress_00':
  p['start']=5.;p['duration']=17.;p['audio_start']+=2
  for c in p['captions']:c['start']+=2;c['end']+=2
# Recover missing individual voice clips from the retained music-free master if needed.
missing=[p for p in parts if not Path(p['file']).exists()]
if missing:
 master=read_audio(ROOT/'audio/Actresses_Narration.opus')
 previous={p['id']:p for p in base['parts']}
 for p in missing:
  old=previous[p['id']];a=round(old['audio_start']*SR);b=a+round(old['audio_duration']*SR)
  target=CACHE/'audio'/f'{p["id"]}_restored.wav';writewav(target,master[a:b]);p['file']=str(target)
data.update(duration=480,opening_setup_seconds=2,first_guess_start_seconds=2,first_name_reveal_seconds=5,second_name_reveal_seconds=25)
(ROOT/'timing_enhanced.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
# Full English subtitles, including the new spoken hook.
import textwrap
cues=[c for p in parts for c in p['captions']];out=[]
for i,c in enumerate(cues,1):out.append(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n'+ '\n'.join(textwrap.wrap(c['text'],width=64,break_long_words=False))+'\n')
(ROOT/'output/Actresses_Enhanced_EN.srt').write_text('\n'.join(out))
(ROOT/'output/Actresses_Enhanced_Script.txt').write_text('\n\n'.join(p['caption'] for p in parts))
voice=np.zeros(480*SR,np.float32)
for p in parts:
 a=read_audio(p['file']);start=round(p['audio_start']*SR);voice[start:start+len(a)]+=a
 assert p['audio_start']+len(a)/SR<=p['start']+p['duration']+.015,p['id']
writewav(CACHE/'narration.wav',voice)
(ROOT/'audio').mkdir(exist_ok=True)
subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(CACHE/'narration.wav'),'-c:a','libopus','-b:a','56k','-application','voip',str(ROOT/'audio/Actresses_Narration_Enhanced.opus')],check=True)
# Same score and balance as the approved episode, with a small opening rise.
music_path=Path('/home/user/.cache/hollywood_actresses/Dream_Culture_Kevin_MacLeod.mp3')
if not music_path.exists():
 import requests
 url='https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dream%20Culture.mp3';r=requests.get(url,timeout=60);r.raise_for_status();music_path.parent.mkdir(parents=True,exist_ok=True);music_path.write_bytes(r.content)
r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(music_path),'-af','highpass=f=50,equalizer=f=2500:t=q:w=0.8:g=-2.5','-f','f32le','-ac','2','-ar',str(SR),'pipe:1'],capture_output=True,check=True)
music=np.frombuffer(r.stdout,dtype='<f4').reshape(-1,2).copy();n=480*SR;mix=np.zeros((n,2),np.float32)
first=music[:int(207.5*SR)];mix[:len(first)]=first;cross=int(60/70*4*SR);pos=len(first)-cross;cycle=music[12*SR:int(207.5*SR)]
while pos<n:
 count=min(len(cycle),n-pos);addition=cycle[:count].copy();length=min(cross,count);theta=np.linspace(0,np.pi/2,length)
 mix[pos:pos+length]*=np.cos(theta)[:,None];addition[:length]*=np.sin(theta)[:,None];mix[pos:pos+count]+=addition;pos+=len(cycle)-cross
mix*=.078/max(float(np.sqrt(np.mean(mix*mix))),1e-6)
envelope=np.ones(n,np.float32);duck=.49
for p in parts:
 a=max(0,int((p['audio_start']-.07)*SR));b=min(n,int((p['audio_start']+p['audio_duration']+.07)*SR));lo=max(0,a-int(.18*SR));hi=min(n,b+int(.45*SR))
 envelope[lo:a]=np.minimum(envelope[lo:a],np.linspace(1,duck,a-lo));envelope[a:b]=np.minimum(envelope[a:b],duck);envelope[b:hi]=np.minimum(envelope[b:hi],np.linspace(duck,1,hi-b))
mix*=envelope[:,None];mix[:int(.3*SR)]*=np.linspace(0,1,int(.3*SR))[:,None];mix[-3*SR:]*=np.linspace(1,0,3*SR)[:,None]
events=[(4.,False),(5.,True)]
for p in parts:
 if p['kind']=='actress' and p['actor']>0:
  events += [(p['start']+i,False) for i in [0.,1.,2.]];events.append((p['start']+3.,True))
for start,reveal in events:
 length=.105 if reveal else .065;t=np.arange(int(length*SR))/SR;freq=1175 if reveal else 780
 sound=(np.sin(2*np.pi*freq*t)+.28*np.sin(2*np.pi*freq*1.5*t))*np.exp(-t/(.027 if reveal else .015))*(.022 if reveal else .014)
 k=int(start*SR);mix[k:k+len(sound)]+=sound[:,None]
# A quiet, original stereo riser supports the two-second photo montage.
rng=np.random.default_rng(492);length=1.72;t=np.arange(round(length*SR))/SR
sw=sosfilt(butter(2,[1000,4800],fs=SR,btype='bandpass',output='sos'),rng.normal(size=len(t)))
sw=(sw*np.sin(np.pi*t/length)**2*.010).astype(np.float32);k=int(.18*SR);pan=np.linspace(0,np.pi/2,len(sw));mix[k:k+len(sw)]+=sw[:,None]*np.stack([np.cos(pan),np.sin(pan)],axis=1)
mix+=voice[:,None];peak=float(np.max(np.abs(mix)))
if peak>.94:mix*=.94/peak
writewav(CACHE/'master.wav',mix)
(ROOT/'work/enhanced_audio_notes.json').write_text(json.dumps({'hook':HOOK,'hook_duration':len(hook)/SR,'opening_setup_seconds':2,'first_guess_start':2,'first_name_reveal':5,'first_story_start':5.34,'full_duration':480,'peak_before_headroom_gain':peak,'same_actor_narrations':True},indent=2))
print('ENHANCED_AUDIO_READY',len(hook)/SR,'second hook; full program 480 seconds.',flush=True)

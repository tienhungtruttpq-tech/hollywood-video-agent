from pathlib import Path
import subprocess,json,wave,math
import numpy as np
from scipy.signal import butter,sosfilt,resample_poly
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent;CACHE=Path('/home/user/.cache/hollywood_actresses')
FF=imageio_ffmpeg.get_ffmpeg_exe();SR=24000;TOTAL=480

def read_audio(path,channels=1):
 p=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(path),'-f','f32le','-ac',str(channels),'-ar',str(SR),'pipe:1'],capture_output=True,check=True)
 a=np.frombuffer(p.stdout,dtype='<f4').copy();return a.reshape(-1,channels) if channels>1 else a

def writewav(path,data):
 with wave.open(str(path),'wb') as w:
  w.setnchannels(1 if data.ndim==1 else data.shape[1]);w.setsampwidth(2);w.setframerate(SR)
  w.writeframes((np.clip(data,-1,1)*32767).astype('<i2').tobytes())

def build_mix(parts):
 n=TOTAL*SR;voice=np.zeros(n,np.float32)
 for p in parts:
  a=read_audio(p['file']);start=round(p['audio_start']*SR);voice[start:start+len(a)]+=a
 writewav(CACHE/'narration.wav',voice)
 # Persist a compact, separate narration master for later visual revisions.
 (ROOT/'audio').mkdir(exist_ok=True)
 subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(CACHE/'narration.wav'),'-c:a','libopus','-b:a','56k','-application','voip',str(ROOT/'audio/Actresses_Narration.opus')],check=True)
 music_file=Path('/home/user/hollywood_full/assets/Dream_Culture_Kevin_MacLeod.mp3')
 if not music_file.exists():music_file=Path('/home/user/.cache/hollywood_actresses/Dream_Culture_Kevin_MacLeod.mp3')
 r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(music_file),'-af','highpass=f=50,equalizer=f=2500:t=q:w=0.8:g=-2.5','-f','f32le','-ac','2','-ar',str(SR),'pipe:1'],capture_output=True,check=True)
 music=np.frombuffer(r.stdout,dtype='<f4').reshape(-1,2).copy();del r
 master=np.zeros((n,2),np.float32);segment=music[:int(207.5*SR)];master[:len(segment)]=segment
 overlap=int(60/70*4*SR);pos=len(segment)-overlap;cycle=music[12*SR:int(207.5*SR)]
 while pos<n:
  count=min(len(cycle),n-pos);a=cycle[:count].copy();c=min(overlap,count);theta=np.linspace(0,np.pi/2,c,dtype=np.float32)
  master[pos:pos+c]*=np.cos(theta)[:,None];a[:c]*=np.sin(theta)[:,None];master[pos:pos+count]+=a;pos+=len(cycle)-overlap
 master*=.078/max(float(np.sqrt(np.mean(master*master))),1e-6)
 gain=np.ones(n,np.float32);duck=.49
 for p in parts:
  a=max(0,int((p['audio_start']-.07)*SR));b=min(n,int((p['audio_start']+p['audio_duration']+.07)*SR))
  lo=max(0,a-int(.18*SR));hi=min(n,b+int(.45*SR))
  gain[lo:a]=np.minimum(gain[lo:a],np.linspace(1,duck,a-lo));gain[a:b]=np.minimum(gain[a:b],duck)
  gain[b:hi]=np.minimum(gain[b:hi],np.linspace(duck,1,hi-b))
 master*=gain[:,None]
 master[:int(.30*SR)]*=np.linspace(0,1,int(.30*SR))[:,None]
 master[-3*SR:]*=np.linspace(1,0,3*SR)[:,None]
 # Original gentle countdown ticks. There are no new spoken clues to overlap.
 events=[]
 for p in parts:
  if p['kind']=='actress' and p['actor']>0:
   events += [(p['start']+k,False) for k in [0.,1.,2.]]
   events.append((p['start']+3.,True))
 events.append((3.,True))
 for start,reveal in events:
  length=.105 if reveal else .065;t=np.arange(int(length*SR))/SR
  f=1175 if reveal else 780
  sound=(np.sin(2*np.pi*f*t)+.28*np.sin(2*np.pi*f*1.5*t))*np.exp(-t/(.027 if reveal else .015))
  sound*=.022 if reveal else .014;k=int(start*SR);end=min(n,k+len(sound));master[k:end]+=sound[:end-k,None]
 master+=voice[:,None];peak=float(np.max(np.abs(master)))
 if peak>.94:master*=.94/peak
 writewav(CACHE/'master.wav',master)
 (ROOT/'work/mix_notes.json').write_text(json.dumps({'duration':480,'music':'Dream Culture — Kevin MacLeod','music_break_rms_target':.078,'duck_gain':duck,'voice_seconds':sum(p['audio_duration'] for p in parts),'peak_before_global_gain':peak,'tick_count':len(events),'narration_master':'audio/Actresses_Narration.opus'},indent=2))
 print('EPISODE_MIX_READY',flush=True)

if __name__=='__main__':build_mix(json.loads((ROOT/'timing.json').read_text())['parts'])

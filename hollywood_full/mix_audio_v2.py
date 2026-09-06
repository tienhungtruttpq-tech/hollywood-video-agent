from pathlib import Path
import json,subprocess,math,wave
import numpy as np
from scipy.signal import butter,sosfilt
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_full');CACHE.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();SR=24000;TOTAL=480.
def writewav(path,data,rate=SR):
    pcm=(np.clip(data,-1,1)*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1 if data.ndim==1 else data.shape[1]);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
def main():
    parts=json.loads((ROOT/'timing.json').read_text())['parts']
    r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str((ROOT/'audio/Narration_English.flac') if (ROOT/'audio/Narration_English.flac').exists() else (ROOT/'audio/Narration_English.opus')),'-f','f32le','-ac','1','-ar',str(SR),'pipe:1'],capture_output=True,check=True)
    voice=np.frombuffer(r.stdout,dtype='<f4').copy();n=int(TOTAL*SR)
    assert len(voice)==n
    music_file=ROOT/'assets/Dream_Culture_Kevin_MacLeod.mp3'
    if not music_file.exists():music_file=Path('/home/user/.cache/hollywood_actresses/Dream_Culture_Kevin_MacLeod.mp3')
    r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(music_file),'-af','highpass=f=50,equalizer=f=2500:t=q:w=0.8:g=-2.5','-f','f32le','-ac','2','-ar',str(SR),'pipe:1'],capture_output=True,check=True)
    music=np.frombuffer(r.stdout,dtype='<f4').reshape(-1,2).copy();del r
    # Repeat the licensed score musically with equal-power, four-beat crossfades.
    # Retain the track's opening for the introduction; subsequent cycles begin
    # after the opening so the rhythm does not repeatedly restart from silence.
    master=np.zeros((n,2),dtype=np.float32)
    segment=music[:int(207.5*SR)];master[:len(segment)]+=segment
    overlap=int((60/70*4)*SR);pos=len(segment)-overlap
    cycle=music[int(12*SR):int(207.5*SR)]
    while pos<n:
        count=min(len(cycle),n-pos);addition=cycle[:count].copy()
        cross=min(overlap,count)
        theta=np.linspace(0,np.pi/2,cross,dtype=np.float32)
        master[pos:pos+cross]*=np.cos(theta)[:,None]
        addition[:cross]*=np.sin(theta)[:,None]
        master[pos:pos+count]+=addition
        pos+=len(cycle)-overlap
    # Clear audible music at breaks; six dB lower under narration; the bed is stronger than V1.
    music_rms=float(np.sqrt(np.mean(master**2)))
    master*=.09/max(music_rms,1e-6)
    gain=np.ones(n,dtype=np.float32)
    duck=.50
    for p in parts:
        a=int(max(0,p['audio_start']-.12)*SR);b=min(n,int((p['audio_start']+p['audio_duration']+.12)*SR))
        attack=int(.24*SR);release=int(.65*SR)
        lo=max(0,a-attack);hi=min(n,b+release)
        gain[lo:a]=np.minimum(gain[lo:a],np.linspace(1,duck,max(0,a-lo),dtype=np.float32))
        gain[a:b]=np.minimum(gain[a:b],duck)
        gain[b:hi]=np.minimum(gain[b:hi],np.linspace(duck,1,max(0,hi-b),dtype=np.float32))
    master*=gain[:,None]
    fadein=int(.65*SR);fadeout=int(3.3*SR)
    master[:fadein]*=np.linspace(0,1,fadein)[:,None]
    master[-fadeout:]*=np.linspace(1,0,fadeout)[:,None]
    del music,segment,cycle,gain
    # Small, original swishes/shutter accents emphasize transitions, not faces.
    rng=np.random.default_rng(2306)
    events=[]
    for p in parts:
        if not p['id'].startswith('actor'):continue
        events.append((p['start'],.015))
        events.append((p['start']+p['reveal'],.023))
    for start,level in events:
        length=.40;t=np.arange(int(length*SR))/SR
        noise=rng.normal(0,1,len(t)).astype(np.float32)
        sound=sosfilt(butter(2,[900,5000],fs=SR,btype='bandpass',output='sos'),noise)
        sound=(sound*np.sin(np.pi*t/length)**3*level).astype(np.float32)
        k=max(0,int((start-.07)*SR));end=min(n,k+len(sound));stereo=np.stack([np.cos(np.linspace(0,np.pi/2,len(sound))),np.sin(np.linspace(0,np.pi/2,len(sound)))],axis=1)
        master[k:end]+=sound[:end-k,None]*stereo[:end-k]
    master+=voice[:,None]
    peak=float(np.max(np.abs(master)))
    if peak>.94:master*=.94/peak
    writewav(CACHE/'master_mix_v2.wav',master)
    metrics={'music_source_rms':music_rms,'music_target_break_rms':.09,'music_under_speech_gain_vs_v1_db':20*math.log10((.09*.5)/(.075*.36)),'music_eq':'50 Hz high-pass; 2.5 kHz -2.5 dB bell to leave space for speech','music_duck_gain':duck,
             'music_duck_db':20*math.log10(duck),'mix_peak_before_loudness_normalization':peak,
             'narration_seconds':sum(p['audio_duration'] for p in parts),'full_duration':TOTAL}
    (ROOT/'work/audio_mix_v2_notes.json').write_text(json.dumps(metrics,indent=2))
    print('V2: 480-second master ready; music is 4.44 dB stronger relative to narration in the ducked sections.',flush=True)

if __name__=="__main__":main()

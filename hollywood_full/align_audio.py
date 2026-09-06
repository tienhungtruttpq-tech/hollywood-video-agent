"""Align batch narration to 32 timed sections, then mix an audible licensed score."""
from pathlib import Path
import os,re,json,wave,subprocess,difflib,math
os.environ['HF_HUB_DISABLE_XET']='1'
import numpy as np
from scipy.signal import resample_poly, butter, sosfilt
from faster_whisper import WhisperModel
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_full');TTS=CACHE/'tts';OUT=ROOT/'output'
for p in [CACHE/'aligned',ROOT/'audio',OUT]:p.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();NARR=json.loads((ROOT/'narrative.json').read_text());PARTS={p['id']:p for p in NARR['parts']}
SR=24000;TOTAL=480.
UNITS=['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen']
TENS=['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
def say_number(n):
    if n<20:return UNITS[n]
    if n<100:return TENS[n//10]+(' '+UNITS[n%10] if n%10 else '')
    if 1900<=n<2000:return 'nineteen '+say_number(n-1900)
    if n==2000:return 'two thousand'
    if 2000<n<2010:return 'two thousand '+say_number(n-2000)
    if 2010<=n<2100:return 'twenty '+say_number(n-2000)
    return str(n)
def tokens(text):
    text=text.lower().replace('’',"'")
    text=re.sub(r'\bjr\.?\b','junior',text)
    text=re.sub(r'\b\d+\b',lambda m:say_number(int(m.group())),text)
    return re.findall(r'[a-z]+',text)
def readwav(path):
    with wave.open(str(path),'rb') as w:
        rate=w.getframerate();chan=w.getnchannels();assert w.getsampwidth()==2
        a=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
        if chan>1:a=a.reshape(-1,chan).mean(axis=1)
    if rate!=SR:a=resample_poly(a,SR,rate).astype(np.float32)
    return a

def writewav(path,data,rate=SR):
    pcm=(np.clip(data,-1,1)*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1 if data.ndim==1 else data.shape[1]);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())

def transcribe_batches():
    model=None
    for b in NARR['batches']:
        output=CACHE/'aligned'/f'asr_{b["index"]:02d}.json'
        if output.exists():continue
        if model is None:model=WhisperModel('base.en',device='cpu',compute_type='int8',cpu_threads=4,download_root=str(CACHE/'asr'))
        names=', '.join(PARTS[p].get('name','') for p in b['parts'])
        segs,info=model.transcribe(str(TTS/b['file']),language='en',beam_size=5,word_timestamps=True,
                                  condition_on_previous_text=False,vad_filter=True,
                                  initial_prompt='Hollywood actors. '+names)
        words=[];texts=[]
        for seg in segs:
            texts.append(seg.text)
            for w in seg.words or []:words.append(dict(word=w.word,start=w.start,end=w.end,probability=w.probability))
        output.write_text(json.dumps(dict(duration=info.duration,text=' '.join(texts),words=words),indent=2))
        print(f'ASR {b["index"]}: {info.duration:.2f}s / '+ ' '.join(texts)[:100],flush=True)
    del model

def align_parts():
    result=[]
    for b in NARR['batches']:
        asr=json.loads((CACHE/'aligned'/f'asr_{b["index"]:02d}.json').read_text())
        words=asr['words'];actual=[];times=[]
        for w in words:
            ts=tokens(w['word'])
            for i,tok in enumerate(ts):
                actual.append(tok);times.append([w['start']+(w['end']-w['start'])*i/max(1,len(ts)),w['start']+(w['end']-w['start'])*(i+1)/max(1,len(ts))])
        expected=[];part_ranges={}
        for pid in b['parts']:
            t=tokens(PARTS[pid]['text']);part_ranges[pid]=(len(expected),len(expected)+len(t));expected+=t
        sm=difflib.SequenceMatcher(None,expected,actual,autojunk=False)
        mapping={}
        for match in sm.get_matching_blocks():
            for k in range(match.size):mapping[match.a+k]=match.b+k
        audio=readwav(TTS/b['file']);duration=len(audio)/SR
        starts=[]
        for idx,pid in enumerate(b['parts']):
            a,z=part_ranges[pid]
            matches=[(e,mapping[e]) for e in range(a,min(z,a+7)) if e in mapping]
            if not matches:raise RuntimeError('Missing narration boundary: '+pid)
            e,j=matches[0]
            t=times[j][0]-.18
            if e>a:t-=min(.5,(e-a)*.18)
            starts.append(max(0,t))
        # Split in the quiet gap just before each next actor, not through a word.
        boundaries=[0.]
        for start in starts[1:]:
            lo=max(boundaries[-1]+.3,start-.12);hi=min(duration-.1,start+.06)
            window=audio[int(lo*SR):int(hi*SR)]
            win=int(.025*SR)
            if len(window)>win:
                power=np.convolve(window**2,np.ones(win)/win,mode='valid')
                cut=lo+(int(np.argmin(power))+win/2)/SR
            else:cut=start
            boundaries.append(cut)
        boundaries.append(duration)
        for k,pid in enumerate(b['parts']):
            part=dict(PARTS[pid]);a,z=part_ranges[pid]
            left,right=boundaries[k],boundaries[k+1]
            chunk=audio[int(left*SR):int(right*SR)]
            # Trim redundant batch pauses, retaining consonants and natural breath.
            nz=np.flatnonzero(np.abs(chunk)>.003)
            trim_start=max(0,int(nz[0])-.12*SR) if len(nz) else 0
            trim_end=min(len(chunk),int(nz[-1])+.20*SR) if len(nz) else len(chunk)
            trim_start=int(trim_start);trim_end=int(trim_end)
            chunk=chunk[trim_start:trim_end];source_start=left+trim_start/SR
            dur=len(chunk)/SR
            lead=.42 if pid.startswith('actor') else .30
            room=part['duration']-lead-.38
            speed=max(1.,dur/room)
            if speed>1.30:raise RuntimeError(f'Excessively long narration for {pid}: {dur:.2f}s')
            inp=CACHE/'aligned'/f'{pid}_raw.wav';out=CACHE/'aligned'/f'{pid}.wav'
            writewav(inp,chunk)
            if speed>1.001:
                subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(inp),'-af',f'atempo={speed:.7f}',str(out)],check=True)
                chunk=readwav(out)
            else:writewav(out,chunk)
            active=chunk[np.abs(chunk)>.013]
            rms=float(np.sqrt(np.mean(active**2))) if len(active) else .1
            gain=min(1.9,.15/max(rms,1e-5),.87/max(float(np.max(np.abs(chunk))),1e-5))
            chunk*=gain;writewav(out,chunk)
            part.update(file=str(out),audio_start=part['start']+lead,audio_duration=len(chunk)/SR,speed=speed,source_duration=dur,source_offset=source_start,batch=b['index'])
            # Sentence boundaries aligned to the recognized words in this batch.
            voice_sent=re.split(r'(?<=[.!?])\s+',part['text'])
            cap_sent=re.split(r'(?<=[!?])\s+|(?<=[.])\s+(?!Jackson)',part['caption'].replace('Jr.','Jr').replace('L. Jackson','L Jackson'))
            if len(cap_sent)!=len(voice_sent):cap_sent=voice_sent
            cu=[];offset=a
            for si,(sentence,cap) in enumerate(zip(voice_sent,cap_sent)):
                n=len(tokens(sentence));end_e=offset+n
                candidates=[mapping[q] for q in range(offset,min(end_e,offset+6)) if q in mapping]
                t0=times[candidates[0]][0] if candidates else source_start
                candidates=[mapping[q] for q in range(max(offset,end_e-6),end_e) if q in mapping]
                t1=times[candidates[-1]][1] if candidates else source_start+dur
                local0=max(0,(t0-source_start)/speed);local1=min(part['audio_duration'],(t1-source_start)/speed+.12)
                cu.append(dict(start=part['audio_start']+local0,end=part['audio_start']+max(local1,local0+.2),text=cap.strip()))
                offset=end_e
            for j in range(len(cu)-1):cu[j]['end']=min(cu[j+1]['start'],cu[j]['end']+.16)
            part['captions']=cu
            if pid.startswith('actor'):
                # Reveal the later image during the first date sentence, then hold
                # both portraits for the career note. Avoid hiding it for too long.
                first_end=(cu[0]['end']-part['start']) if cu else 5.
                part['reveal']=max(3.4,min(5.1,first_end-1.1))
                part['reveal']=round(part['reveal']/(60/70/2))*(60/70/2)
            result.append(part)
            matched=sum(1 for q in range(a,z) if q in mapping)/(z-a)
            print(f'{pid:10s} original {dur:5.2f}s -> {part["audio_duration"]:5.2f}s | speed {speed:.3f} | text match {matched:.1%}',flush=True)
    result.sort(key=lambda x:x['start'])
    (ROOT/'timing.json').write_text(json.dumps({'duration':480,'parts':result},indent=2))
    return result

def srt_time(t):
    ms=int(round(t*1000));return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
def write_srt(parts):
    import textwrap
    cues=[c for p in parts for c in p['captions']]
    text=[]
    for i,c in enumerate(cues,1):
        lines='\n'.join(textwrap.wrap(c['text'],width=48,break_long_words=False))
        text.append(f'{i}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{lines}\n')
    (OUT/'Hollywood_Then_Now_8min_EN.srt').write_text('\n'.join(text))

def music_credit_master(parts):
    n=int(TOTAL*SR);voice=np.zeros(n,dtype=np.float32)
    for p in parts:
        a=readwav(p['file']);k=round(p['audio_start']*SR);voice[k:k+len(a)]+=a
    vpath=CACHE/'narration.wav';writewav(vpath,voice)
    subprocess.run([FF,'-hide_banner','-loglevel','error','-y','-i',str(vpath),'-c:a','flac','-compression_level','8',str(ROOT/'audio/Narration_English.flac')],check=True)
    print('Narration master saved.',flush=True)
    music_file=ROOT/'assets/Dream_Culture_Kevin_MacLeod.mp3'
    r=subprocess.run([FF,'-hide_banner','-loglevel','error','-i',str(music_file),'-f','f32le','-ac','2','-ar',str(SR),'pipe:1'],capture_output=True,check=True)
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
    # Clear audible music at breaks; approximately nine dB lower under narration.
    music_rms=float(np.sqrt(np.mean(master**2)))
    master*=.075/max(music_rms,1e-6)
    gain=np.ones(n,dtype=np.float32)
    duck=.36
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
        events.append((p['start'],.010))
        events.append((p['start']+p['reveal'],.015))
    for start,level in events:
        length=.32;t=np.arange(int(length*SR))/SR
        noise=rng.normal(0,1,len(t)).astype(np.float32)
        sound=sosfilt(butter(2,[900,5000],fs=SR,btype='bandpass',output='sos'),noise)
        sound=(sound*np.sin(np.pi*t/length)**3*level).astype(np.float32)
        k=max(0,int((start-.07)*SR));end=min(n,k+len(sound));master[k:end]+=sound[:end-k,None]
    master+=voice[:,None]
    peak=float(np.max(np.abs(master)))
    if peak>.94:master*=.94/peak
    writewav(CACHE/'master_mix.wav',master)
    metrics={'music_source_rms':music_rms,'music_target_break_rms':.075,'music_duck_gain':duck,
             'music_duck_db':20*math.log10(duck),'mix_peak_before_loudness_normalization':peak,
             'narration_seconds':sum(p['audio_duration'] for p in parts),'full_duration':TOTAL}
    (ROOT/'work/audio_mix_notes.json').write_text(json.dumps(metrics,indent=2))
    print('480-second voice + music master ready.',flush=True)

if __name__=='__main__':
    transcribe_batches();parts=align_parts();write_srt(parts);music_credit_master(parts)
    print('AUDIO_COMPLETE',flush=True)

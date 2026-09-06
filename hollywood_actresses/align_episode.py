"""Align batch narration to 32 timed sections, then mix an audible licensed score."""
from pathlib import Path
import os,re,json,wave,subprocess,difflib,math,unicodedata
os.environ['HF_HUB_DISABLE_XET']='1'
import numpy as np
from scipy.signal import resample_poly, butter, sosfilt
from faster_whisper import WhisperModel
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_actresses');TTS=CACHE/'audio';OUT=ROOT/'output'
for p in [CACHE/'aligned',ROOT/'audio',OUT]:p.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe();NARR=json.loads((ROOT/'narrative.json').read_text());PARTS={p['id']:p for p in NARR['parts']}
OVERRIDES=json.loads((ROOT/'audio_overrides.json').read_text()) if (ROOT/'audio_overrides.json').exists() else {}
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
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower().replace('’',"'")
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
        if model is None:model=WhisperModel('base.en',device='cpu',compute_type='int8',cpu_threads=4,download_root='/home/user/.cache/hollywood_full/asr')
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
            if pid in OVERRIDES:
                override=OVERRIDES[pid];chunk=readwav(Path(override['file']))
                nz=np.flatnonzero(np.abs(chunk)>.003)
                if len(nz):
                    left_sample=max(0,int(nz[0])-int(.08*SR));right_sample=min(len(chunk),int(nz[-1])+int(.15*SR))
                    chunk=chunk[left_sample:right_sample]
                part['text']=override['text'];part['caption']=override.get('caption',override['text']);part['override']=override['file']
                source_start=0
            dur=len(chunk)/SR
            lead=part.get('lead',.2)+part.get('guess',0.)
            room=part['duration']-lead-.24
            speed=max(1.,dur/room)
            if speed>(1.45 if part['kind'] in ['intro','interlude','outro'] else 1.25):raise RuntimeError(f'Excessively long narration for {pid}: {dur:.2f}s')
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
            if cu:
                cu[0]['start']=part['audio_start'];cu[-1]['end']=part['audio_start']+part['audio_duration']
            if pid in OVERRIDES:
                cu=[dict(start=part['audio_start'],end=part['audio_start']+part['audio_duration'],text=part['caption'])]
            part['captions']=cu
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
        lines='\n'.join(textwrap.wrap(c['text'],width=64,break_long_words=False))
        text.append(f'{i}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{lines}\n')
    (OUT/'Actresses_Then_Now_EN.srt').write_text('\n'.join(text))

def music_credit_master(parts):
    from mix_episode import build_mix
    build_mix(parts)

if __name__=='__main__':
    transcribe_batches();parts=align_parts();write_srt(parts);music_credit_master(parts)
    print('AUDIO_COMPLETE',flush=True)

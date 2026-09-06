from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
backup=ROOT/'versions/v1';backup.mkdir(parents=True,exist_ok=True)
for name in ['render_full.py','mix_audio.py','validate_video.py','README.md']:
    dest=backup/name
    if not dest.exists():shutil.copy2(ROOT/name,dest)

s=(ROOT/'render_full.py').read_text()
s=s.replace("RENDER=CACHE/'render'","RENDER=CACHE/'render_v2'")
s=s.replace("amount=.012 if min(native)<450 else .024","amount=.012 if min(native)<450 else .032")
s=s.replace("mode=i%4","mode=[5,0,4,1,3,2][i%6]")
s=s.replace("PLACEHOLDERS={}","PLACEHOLDERS={};HOLD_BLANK={}")
s=s.replace("        track(d,(242,176),'FAST FORWARD'", "        HOLD_BLANK[i]=np.asarray(im.copy())\n        track(d,(242,176),'FAST FORWARD'")
s=s.replace("p=ease(q);a=np.asarray(photo);b=hold_image(i);mode=", "p=ease(q);a=np.asarray(photo);b=hold_image(i)\n    fade=ease(q/.25);b=(b*(1-fade)+HOLD_BLANK[i]*fade).astype(np.uint8)\n    mode=")
old="""    else:
        off=round(484*(1-p));result=b.copy()
        if off<484:result[:,off:]=a[:,:484-off]
        if 0<off<484:result[:,max(0,off-2):off]=np.array(LAV,dtype=np.uint8)
        return Image.fromarray(result)
    return Image.fromarray((a*mask+b*(1-mask)).astype(np.uint8))"""
new="""    elif mode==3:
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
    return Image.fromarray((a*mask+b*(1-mask)).astype(np.uint8))"""
assert old in s;s=s.replace(old,new)
s=s.replace("phase=(local-part['reveal'])/.76","phase=(local-part['reveal'])/.98")
old="""    d.rectangle((71,107,556,588),outline=LINE,width=1);d.rectangle((723,107,1208,588),outline=LINE,width=1)
    # Thin timeline"""
new="""    d.rectangle((71,107,556,588),outline=LINE,width=1);d.rectangle((723,107,1208,588),outline=LINE,width=1)
    if 0<phase<1:
        # A screen-locked border highlight emphasizes the new photograph.
        glow=math.sin(math.pi*phase)
        edge=tuple(round(LINE[c]*(1-glow)+LAV[c]*glow) for c in range(3))
        d.rectangle((723,107,1208,588),outline=edge,width=2)
    # Thin timeline"""
assert old in s;s=s.replace(old,new)
needle="    if t>DURATION-.55:im=Image.blend(im,Image.new('RGB',(W,H),BG),ease((t-DURATION+.55)/.55))"
new="""    if kind=='actor' and i%5==0 and .18<local<1.18:
        # A restrained warm light-leak sweep, not a white flash or strobe.
        u=(local-.18);xx=np.arange(W,dtype=np.float32)[None,:]
        yy=np.arange(H,dtype=np.float32)[:,None]
        centre=-230+(W+460)*ease(u)
        band=np.exp(-((xx-centre-.16*(yy-H*.5))/118)**2)
        alpha=(band*.14*math.sin(math.pi*u))[:,:,None]
        ar=np.asarray(im,dtype=np.float32)
        ar=ar*(1-alpha)+np.array([249,214,173],np.float32)[None,None,:]*alpha
        im=Image.fromarray(np.clip(ar,0,255).astype(np.uint8))
"""+needle
assert needle in s;s=s.replace(needle,new)
s=s.replace("f'final_layout_{page+1}.jpg'","f'v2_layout_{page+1}.jpg'")
s=s.replace("'Hollywood_8min_Poster.jpg'","'Hollywood_8min_V2_Poster.jpg'")
s=s.replace("'-preset','fast','-crf','20'","'-preset','medium','-crf','23'")
s=s.replace("Full 8-Minute Edition","8-Minute Edition V2 — Enhanced Music & Transitions")
s=s.replace("'render_full.py','actors.json'","'render_v2.py','actors.json'")
s=s.replace("output=OUT/'Hollywood_Then_Now_8min.mp4'","output=OUT/'Hollywood_Then_Now_8min_V2.mp4'")
s=s.replace("mix=CACHE/'master_mix.wav'","mix=CACHE/'master_mix_v2.wav'")
s=s.replace("'-c:v','libx264','-preset','medium','-crf','23','-threads','4','-pix_fmt','yuv420p','-c:a'","'-c:v','copy','-c:a'")
s=s.replace("loudnorm=I=-16:TP=-1.5:LRA=9","loudnorm=I=-15.5:TP=-1.8:LRA=8")
s=s.replace("with align_audio.py first.","with mix_audio_v2.py first.")
(ROOT/'render_v2.py').write_text(s)

s=(ROOT/'mix_audio.py').read_text()
s=s.replace("'-i',str(music_file),'-f'","'-i',str(music_file),'-af','highpass=f=50,equalizer=f=2500:t=q:w=0.8:g=-2.5','-f'")
s=s.replace("approximately nine dB lower under narration.","six dB lower under narration; the bed is stronger than V1.")
s=s.replace("master*=.075/max(music_rms,1e-6)","master*=.09/max(music_rms,1e-6)")
s=s.replace("duck=.36","duck=.50")
s=s.replace("events.append((p['start'],.010))","events.append((p['start'],.015))")
s=s.replace("events.append((p['start']+p['reveal'],.015))","events.append((p['start']+p['reveal'],.023))")
s=s.replace("length=.32;t=", "length=.40;t=")
s=s.replace("master[k:end]+=sound[:end-k,None]", "stereo=np.stack([np.cos(np.linspace(0,np.pi/2,len(sound))),np.sin(np.linspace(0,np.pi/2,len(sound)))],axis=1)\n        master[k:end]+=sound[:end-k,None]*stereo[:end-k]")
s=s.replace("'master_mix.wav'","'master_mix_v2.wav'")
s=s.replace("'music_target_break_rms':.075","'music_target_break_rms':.09,'music_under_speech_gain_vs_v1_db':20*math.log10((.09*.5)/(.075*.36)),'music_eq':'50 Hz high-pass; 2.5 kHz -2.5 dB bell to leave space for speech'")
s=s.replace('work/audio_mix_notes.json','work/audio_mix_v2_notes.json')
s=s.replace("480-second voice + music master ready.","V2: 480-second master ready; music is 4.44 dB stronger relative to narration in the ducked sections.")
(ROOT/'mix_audio_v2.py').write_text(s)

s=(ROOT/'validate_video.py').read_text()
s=s.replace('Hollywood_Then_Now_8min.mp4','Hollywood_Then_Now_8min_V2.mp4')
s=s.replace("f'encoded_review_{page+1}.jpg'","f'v2_encoded_review_{page+1}.jpg'")
s=s.replace('audio_loudness.txt','audio_loudness_v2.txt')
s=s.replace('validation.json','validation_v2.json')
(ROOT/'validate_v2.py').write_text(s)
print('V2 renderer, mixer and validation script created.')

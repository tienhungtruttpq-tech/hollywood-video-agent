from pathlib import Path
ROOT=Path(__file__).resolve().parent
old=Path('/home/user/hollywood_full')
# Reuse the proven alignment machinery with the new quiz timing.
s=(old/'align_audio.py').read_text()
s=s.replace("import os,re,json,wave,subprocess,difflib,math","import os,re,json,wave,subprocess,difflib,math,unicodedata")
s=s.replace("Path('/home/user/.cache/hollywood_full')","Path('/home/user/.cache/hollywood_actresses')")
s=s.replace("TTS=CACHE/'tts'","TTS=CACHE/'audio'")
s=s.replace("download_root=str(CACHE/'asr')","download_root='/home/user/.cache/hollywood_full/asr'")
s=s.replace("text=text.lower().replace('’',\"'\")","text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower().replace('’',\"'\")")
s=s.replace("lead=.42 if pid.startswith('actor') else .30","lead=part.get('lead',.2)+part.get('guess',0.)")
s=s.replace("room=part['duration']-lead-.38","room=part['duration']-lead-.24")
s=s.replace("if speed>1.30:raise RuntimeError", "if speed>(1.45 if part['kind'] in ['intro','interlude','outro'] else 1.25):raise RuntimeError")
s=s.replace("part['captions']=cu","if cu:\n                cu[0]['start']=part['audio_start'];cu[-1]['end']=part['audio_start']+part['audio_duration']\n            part['captions']=cu")
a=s.index("            if pid.startswith('actor'):")
b=s.index("            result.append(part)",a)
s=s[:a]+s[b:]
s=s.replace("width=48","width=64")
s=s.replace('Hollywood_Then_Now_8min_EN.srt','Actresses_Then_Now_EN.srt')
a=s.index('def music_credit_master(parts):');b=s.index("\nif __name__",a)
s=s[:a]+'''def music_credit_master(parts):
    from mix_episode import build_mix
    build_mix(parts)
'''+s[b:]
(ROOT/'align_episode.py').write_text(s)
# Geometric crop suggestions; all are reviewed before the final video.
s=(old/'prepare_photos.py').read_text().replace('/home/user/.cache/hollywood_full/prepared','/home/user/.cache/hollywood_actresses/prepared')
s=s.replace("distance=(cx-target[0])**2+(cy-target[1])**2", "distance=(cx-target[0])**2+(cy-target[1])**2\n        if distance>.26**2:continue")
s=s.replace("side=min(max(w*2.1,h*2.1),iw,ih)","side=min(max(w*2.25,h*2.25,min(iw,ih)*.70),iw,ih)")
(ROOT/'prepare_photos.py').write_text(s)
print('Episode production helpers prepared.')

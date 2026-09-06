import sys,json,requests,concurrent.futures,hashlib,shutil
from pathlib import Path
from PIL import Image,ImageOps
sys.path.insert(0,str(Path(__file__).parent));import source_photos as s
ROOT=s.ROOT;assets=ROOT/'assets/photos';assets.mkdir(parents=True,exist_ok=True)
C=json.loads((ROOT/'research/candidates.json').read_text());CAST=json.loads((ROOT/'research/cast.json').read_text())
PICKS={(16,'now'):1,(20,'then'):1,(20,'now'):1,(22,'now'):1,(26,'now'):1}
# Explicit framing anchors for source photos containing multiple people. These
# are compositional locations, not face-recognition identities.
ANCHORS={(6,'then'):(.32,.36),(10,'now'):(.57,.30),
         (11,'then'):(.42,.35),(21,'then'):(.865,.30),(22,'now'):(.75,.26)}
# Preserve exactly the three framing decisions approved in the first demo.
LOCKED={(0,'then'):[85/669,62/1024,487/669,485/1024],
        (2,'now'):[1060/3840,300/2746,2230/3840,1860/2746]}

def job(task):
 i,era=task;p=dict(C[f'{i:02d}_{era}'][PICKS.get((i,era),0)]);yr=p['year']
 url=p['url'];fn=f'{i:02d}_{era}_{hashlib.sha1(url.encode()).hexdigest()[:8]}.jpg';dest=assets/fn
 if not dest.exists():
  if p.get('reuse_path'):im=Image.open(p['reuse_path']).convert('RGB')
  else:
   width=1920 if (i,era) in [(21,'then'),(10,'now')] else 1280
   if p['width']>width:
    dl=url.replace('upload.wikimedia.org/wikipedia/commons/','thumb.wikimedia.org/wikipedia/commons/thumb/')+'/'+str(width)+'px-'+url.split('/')[-1]
   else:dl=url
   r=requests.get(dl,headers=s.HEAD,timeout=45)
   if not r.ok and p['width']>500:
    # Use the official cached thumbnail size if the original is temporarily rate limited.
    dl=url.replace('upload.wikimedia.org/wikipedia/commons/','thumb.wikimedia.org/wikipedia/commons/thumb/')+'/500px-'+url.split('/')[-1]
    r=requests.get(dl,headers=s.HEAD,timeout=40)
   import io
   if r.ok:
    im=Image.open(io.BytesIO(r.content)).convert('RGB');p['download']=dl
   elif p.get('preview') and Path(p['preview']).is_file():
    # Respect origin rate limits: reuse the already downloaded, source-matched thumbnail.
    im=Image.open(p['preview']).convert('RGB');p['resolution_note']='Uses the previously downloaded official thumbnail; origin was rate limited.'
   else:r.raise_for_status()
  # Retain generous resolution for manual reframing without persisting giant originals.
  im.thumbnail((2400,3000),Image.Resampling.LANCZOS)
  im.save(dest,quality=94,optimize=True)
 p['file']='photos/'+fn;p['downloaded_size']=list(Image.open(dest).size)
 p['anchor']=list(ANCHORS.get((i,era),(.5,.33)))
 if (i,era) in LOCKED:p['locked_crop']=LOCKED[i,era]
 p.pop('preview',None);p.pop('score',None);p.pop('reuse_path',None)
 return i,era,p
actors=[dict(index=i,name=a['name'],years=list(a['years']),then=None,now=None) for i,a in enumerate(CAST)]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for i,era,p in ex.map(job,[(i,e) for i in range(30) for e in ['then','now']]):
  actors[i][era]=p;actors[i]['years'][0 if era=='then' else 1]=p['year']
  print(i,era,p['downloaded_size'],p['year'],p['title'],flush=True)
for a in actors:a['delta']=a['years'][1]-a['years'][0]
(ROOT/'actors.json').write_text(json.dumps(actors,ensure_ascii=False,indent=2))
shutil.copytree('/home/user/hollywood_demo/assets/fonts',ROOT/'assets/fonts',dirs_exist_ok=True)
print('Saved 60 selected source photographs.')

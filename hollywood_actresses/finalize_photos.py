from pathlib import Path
import json,sys,requests,concurrent.futures,hashlib,io
from PIL import Image
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));import collect_photos as s
CACHE=s.CACHE;(CACHE/'photos').mkdir(parents=True,exist_ok=True)
C=json.loads((ROOT/'research/photo_candidates.json').read_text())
CAST=list(s.CAST)
# A clearly dated television publicity photograph gives the final icon a
# stronger archival comparison; the photograph is explicitly credited as such.
C['23_then']=[s.pool('Meryl Streep',1978)[0]];CAST[23]=('Meryl Streep',1978,2026)
PICKS={(2,'then'):1,(7,'then'):1,(18,'now'):1,(19,'then'):1,(20,'now'):1,(23,'now'):1}
ANCHORS={(8,'now'):(.49,.24),(9,'then'):(.48,.33),(11,'then'):(.43,.39),(20,'then'):(.52,.35)}

def job(task):
 i,e=task;p=dict(C[f'{i:02d}_{e}'][PICKS.get((i,e),0)]);url=p['url']
 fn=f'{i:02d}_{e}_{hashlib.sha1(url.encode()).hexdigest()[:8]}.jpg';dest=CACHE/'photos'/fn
 if not dest.exists():
  width=3840 if (i,e)==(8,'now') else 1280
  dl=url
  if p['width']>width:dl=url.replace('upload.wikimedia.org/wikipedia/commons/','thumb.wikimedia.org/wikipedia/commons/thumb/')+f'/{width}px-'+url.split('/')[-1]
  response=requests.get(dl,headers=s.HEAD,timeout=50)
  if response.ok:im=Image.open(io.BytesIO(response.content)).convert('RGB')
  elif p.get('preview') and Path(p['preview']).is_file():
   im=Image.open(p['preview']).convert('RGB');p['resolution_note']='Previously downloaded official thumbnail used because origin was unavailable.'
  else:response.raise_for_status()
  im.save(dest,quality=94,optimize=True)
 p['file']=str(dest);p['downloaded_size']=list(Image.open(dest).size)
 p['anchor']=list(ANCHORS.get((i,e),(.5,.32)))
 p['context']='On set' if (i,e)==(4,'now') else 'TV publicity photo' if (i,e)==(23,'then') else 'Yearbook photo' if (i,e)==(18,'then') else ''
 for key in ['preview','score']:p.pop(key,None)
 return i,e,p
actors=[dict(index=i,name=n,years=[a,b],then=None,now=None) for i,(n,a,b) in enumerate(CAST)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 for i,e,p in ex.map(job,[(i,e) for i in range(24) for e in ['then','now']]):
  actors[i][e]=p;print(i,e,p['year'],p['downloaded_size'],p['title'],flush=True)
for a in actors:
 a['delta']=a['years'][1]-a['years'][0]
 for e in ['then','now']:
  p=a[e]
  assert str(p['year']) in p['title']+' '+p['date']+' '+p['description'],(a['name'],e,'date needs review')
(ROOT/'actors.json').write_text(json.dumps(actors,ensure_ascii=False,indent=2))
print('48_SELECTED_PHOTOGRAPHS_READY',flush=True)

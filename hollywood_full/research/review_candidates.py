import sys,json,requests,concurrent.futures,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).parent));import source_photos as s
root=s.ROOT;cache=s.CACHE
cast=json.loads((root/'research/cast.json').read_text());candidates=json.loads((root/'research/candidates.json').read_text())
def download(item):
 key,j,p=item
 if 'reuse_path' in p:return key,j,p['reuse_path']
 path=cache/(key+'_'+str(j)+'_'+hashlib.sha1(p['url'].encode()).hexdigest()[:8]+'.jpg')
 if path.exists():return key,j,str(path)
 u=p['url'];w=250
 if p['width']>w:u=u.replace('upload.wikimedia.org/wikipedia/commons/','thumb.wikimedia.org/wikipedia/commons/thumb/')+'/'+str(w)+'px-'+u.split('/')[-1]
 try:
  r=requests.get(u,headers=s.HEAD,timeout=35);r.raise_for_status()
  path.write_bytes(r.content);im=Image.open(path);im.verify()
  return key,j,str(path)
 except Exception as e:return key,j,'ERROR: '+str(e)
tasks=[(key,j,p) for key,a in candidates.items() for j,p in enumerate(a)]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for key,j,path in ex.map(download,tasks):
  candidates[key][j]['preview']=path
  if path.startswith('ERROR'):print(key,j,path,flush=True)
(root/'research/candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
f2=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',17)
for page in range(6):
 cv=Image.new('RGB',(1040,1450),'#161620');d=ImageDraw.Draw(cv)
 for row,i in enumerate(range(page*5,page*5+5)):
  y=row*290
  d.text((10,y+3),f"{i:02d}  {cast[i]['name']}  {cast[i]['years'][0]} / {cast[i]['years'][1]}",font=f2,fill='white')
  for era,offset in [('then',0),('now',2)]:
   a=candidates[f'{i:02d}_{era}']
   for j,p in enumerate(a):
    x=(offset+j)*260;path=p.get('preview','')
    if path and not path.startswith('ERROR'):
     im=Image.open(path).convert('RGB');im.thumbnail((246,224))
     cv.paste(im,(x+(260-im.width)//2,y+30+(224-im.height)//2))
    d.text((x+5,y+256),f'{era.upper()} {j} / '+p['title'].replace('File:','')[:20],font=f,fill='#b8afff')
 cv.save(root/'research'/f'review_{page+1}.jpg',quality=90)
print('Six candidate boards saved.')

"""Create safe, repeatable portrait framing. Detection locates faces, not identities."""
from pathlib import Path
import json,math
import cv2
import numpy as np
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent
CACHE=Path('/home/user/.cache/hollywood_actresses/prepared');CACHE.mkdir(parents=True,exist_ok=True)
FRONTAL=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
PROFILE=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_profileface.xml')
cv2.setNumThreads(2)

def framing(im,photo):
    iw,ih=im.size
    if photo.get('locked_crop'):
        roi=photo['locked_crop'];return [roi[0]*iw,roi[1]*ih,roi[2]*iw,roi[3]*ih],'approved framing'
    target=photo.get('anchor',[.5,.33]);thumb=im.copy();thumb.thumbnail((660,820));arr=np.asarray(thumb)
    gray=cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY);gray=cv2.equalizeHist(gray)
    scale=iw/thumb.width
    boxes=list(FRONTAL.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(28,28)))
    if not boxes:
        boxes=list(PROFILE.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(28,28)))
        flipped=PROFILE.detectMultiScale(gray[:,::-1],scaleFactor=1.1,minNeighbors=5,minSize=(28,28))
        for x,y,w,h in flipped:boxes.append((thumb.width-x-w,y,w,h))
    candidates=[]
    for x,y,w,h in boxes:
        if w*h/(thumb.width*thumb.height)<.006:continue
        cx=(x+w*.5)/thumb.width;cy=(y+h*.5)/thumb.height
        distance=(cx-target[0])**2+(cy-target[1])**2
        if distance>.26**2:continue
        score=-10*distance+.32*math.log(w*h/(thumb.width*thumb.height)+1e-8)
        candidates.append((score,x*scale,y*scale,w*scale,h*scale))
    if candidates:
        _,x,y,w,h=max(candidates)
        side=min(max(w*2.25,h*2.25,min(iw,ih)*.70),iw,ih)
        # Do not exaggerate the grain of very small archival photographs.
        if min(iw,ih)<350:side=min(iw,ih)
        cx=x+w*.5;cy=y+h*.68
        left=max(0,min(iw-side,cx-side*.5));top=max(0,min(ih-side,cy-side*.5))
        return [left,top,left+side,top+side],'geometric face framing'
    side=min(iw,ih)
    left=max(0,min(iw-side,target[0]*iw-side*.5))
    top=max(0,min(ih-side,target[1]*ih-side*.48))
    return [left,top,left+side,top+side],'manual-anchor fallback'

def prepare():
    actors=json.loads((ROOT/'actors.json').read_text())
    previous=json.loads((ROOT/'framing.json').read_text()) if (ROOT/'framing.json').exists() else {}
    out={}
    for a in actors:
        for era in ['then','now']:
            key=f'{a["index"]:02d}_{era}';p=a[era];im=Image.open(ROOT/'assets'/p['file']).convert('RGB')
            if key in previous and previous[key].get('manual'):
                box=previous[key]['box'];method='manual review'
            else:box,method=framing(im,p)
            cropped=im.crop(tuple(round(x) for x in box))
            cropped=ImageOps.fit(cropped,(1040,1040),Image.Resampling.LANCZOS,centering=(.5,.18))
            cropped.save(CACHE/(key+'.jpg'),quality=95,optimize=True)
            out[key]={'source':p['file'],'size':list(im.size),'box':box,'method':method,'manual':method=='manual review'}
            print(key,a['name'],method,[round(x) for x in box],flush=True)
    (ROOT/'framing.json').write_text(json.dumps(out,indent=2))
    return out
if __name__=='__main__':prepare()

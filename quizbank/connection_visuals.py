"""Render only authored original PDF crops; attach exact bytes to reviewed questions."""
import base64
import copy
import hashlib
import threading
from pathlib import Path
import fitz
from studyez_contracts.roots.media import validate_images

# Review batches of one lecture run side by side (docs/changes/2026-11-11-root-batch-parallel). PyMuPDF is not
# thread-safe, and two batches may write the same content-named image copy; one render or copy at a time.
_LOCK = threading.RLock()

def authored(bank):
    """The bank as an authoring model writes it: `stimuli` is renderer-owned (made from visual_stimuli).

    A repair round that showed the model rendered questions got them copied back verbatim, and the
    authoring schema rejected the whole repair (26110901 사슬알균 repair-1)."""
    value=copy.deepcopy(bank)
    for q in value['questions']:q.pop('stimuli',None)
    return value

def render(bank,specs,packet,material):
    with _LOCK:return _render(bank,specs,packet,material)

def _render(bank,specs,packet,material):
    value=copy.deepcopy(bank);qs={q['question_id']:q for q in value['questions']}
    sources={s['id']:s for s in packet['sources']};seen=set()
    for q in qs.values():q.pop('stimuli',None)
    for s in specs:
        key=(s['question_id'],s['source_id'],s['page'],tuple(s['crop']))
        if key in seen or s['question_id']not in qs:raise ValueError('그림의 중복/없는 문항 참조')
        seen.add(key);source=sources.get(s['source_id']);x0,y0,x1,y1=s['crop']
        if source is None or not 0<=x0<x1<=1 or not 0<=y0<y1<=1:raise ValueError('그림 원본/crop 불일치')
        path=Path(source['localPath'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('그림 원본 지문 불일치')
        if s.get('image_id'):
            from .connection_figures import selected
            body,width,height=selected(s,source,material)
        else:
            body,width,height=page_crop(path,s)
        digest=hashlib.sha256(body).hexdigest()
        image={'source_id':s['source_id'],'source_sha256':source['sha256'],'page':s['page'],'crop':s['crop'],
            'sha256':digest,'width':width,'height':height,'png_base64':base64.b64encode(body).decode('ascii')}
        qs[s['question_id']].setdefault('stimuli',[]).append(image)
        target=Path(material)/('stimulus-'+digest+'.png')
        if target.exists():
            if target.read_bytes()!=body:raise ValueError('기존 그림 사본 지문 불일치')
        else:target.write_bytes(body)
    validate_images(value)
    return value


# Render at 2x first (unchanged for every crop that already fits). Photo-heavy notes can exceed
# the 1 MB PNG limit at 2x; then step the scale down deterministically until the bytes fit.
SCALES=(2,1.5,1.25,1,0.75)

def page_crop(path,s,scales=SCALES):
        from studyez_contracts.roots.media import MAX_IMAGE
        x0,y0,x1,y1=s['crop']
        with fitz.open(path)as pdf:
            if not 1<=s['page']<=len(pdf):raise ValueError('그림 원본 물리쪽 불일치')
            page=pdf[s['page']-1];r=page.rect
            clip=fitz.Rect(x0*r.width,y0*r.height,x1*r.width,y1*r.height)
            if clip.width*2>4096 or clip.height*2>4096 or clip.width*clip.height*4>4*1024*1024:
                raise ValueError('그림 crop이 표시·검수 크기 한도를 초과했습니다.')
            for scale in scales:
                pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=clip);body=pix.tobytes('png')
                if len(body)<=MAX_IMAGE:break
            return body,pix.width,pix.height

def paths(bank,material):
    with _LOCK:return _paths(bank,material)

def _paths(bank,material):
    result=[];labels=[]
    validate_images(bank)
    for q in bank['questions']:
        for s in q.get('stimuli',[]):
            path=Path(material)/('stimulus-'+s['sha256']+'.png')
            if not path.exists():path.write_bytes(base64.b64decode(s['png_base64']))
            if hashlib.sha256(path.read_bytes()).hexdigest()!=s['sha256']:raise ValueError('검수용 그림 사본 불일치')
            result.append(path);labels.append({'attachment':len(result),'question_id':q['question_id'],'sha256':s['sha256']})
    return result,labels

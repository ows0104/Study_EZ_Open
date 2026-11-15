"""Bounded immutable PNG question stimuli. No paths, URLs or authored captions.

Photo-import revisions (`photo_import.POLICY`, docs/changes/2026-11-15-photo-quiz-import) may also carry JPEG
bytes in the same `png_base64` field and have higher per-revision limits; every other revision keeps PNG-only
and 64 images / 8 MB."""
import base64
import binascii
import hashlib
import math
import struct
import zlib
from studyez_contracts.learning_links.schema import obj, arr, TEXT, HASH
from studyez_contracts.learning_links.validate import require, validate_shape

BOX=arr({'type':'number','minimum':0,'maximum':1},4)
BOX['maxItems']=4;BOX.pop('uniqueItems',None)
CROP=obj(question_id=TEXT,source_id=TEXT,page={'type':'integer','minimum':1},crop=BOX,reason=TEXT)
IMAGE=obj(source_id=TEXT,source_sha256=HASH,page={'type':'integer','minimum':1},crop=BOX,
          sha256=HASH,width={'type':'integer','minimum':1,'maximum':4096},
          height={'type':'integer','minimum':1,'maximum':4096},png_base64=TEXT)
MAX_IMAGE=1024*1024
MAX_TOTAL=8*1024*1024
MAX_COUNT=64
# Photo-heavy practicals (one histology photo per figure). Per image stays 1 MB.
PHOTO_MAX_TOTAL=24*1024*1024
PHOTO_MAX_COUNT=200
PHOTO_MAX_PIXELS=64*1024*1024
JPEG=b'\xff\xd8\xff'

# A hand-authored photo revision names this method in review.provenance (no generation_policy; the pipeline
# never writes it). Only such a revision gets JPEG and the PHOTO_* limits.
PHOTO_METHOD='photo-import/1'

def photo_import(doc):
    provenance=(doc.get('review')or{}).get('provenance')or{}
    return doc.get('generation_policy')is None and provenance.get('method')==PHOTO_METHOD

def media_type(body):
    return 'image/jpeg' if body[:3]==JPEG else 'image/png'

def public_images(question):
    return [{'sha256':s['sha256'],'width':s['width'],'height':s['height'],
        'url':'data:'+media_type(base64.b64decode(s['png_base64'][:8]))+';base64,'+s['png_base64'],'alt':'문항 그림 '+str(i+1)}for i,s in enumerate(question.get('stimuli',[]))]

def jpeg_size(body):
    """(width, height) from the first SOF marker of a baseline/progressive JPEG; checks markers end to end."""
    require(len(body)>=4 and body[:2]==b'\xff\xd8' and body[-2:]==b'\xff\xd9','stimuli: invalid JPEG')
    offset=2;size=None
    while offset+4<=len(body):
        require(body[offset]==0xff,'stimuli: invalid JPEG marker')
        marker=body[offset+1]
        if marker in(0xd8,0x01)or 0xd0<=marker<=0xd7:offset+=2;continue
        if marker==0xd9:break
        length=struct.unpack('>H',body[offset+2:offset+4])[0]
        require(length>=2 and offset+2+length<=len(body),'stimuli: truncated JPEG')
        if marker in(0xc0,0xc1,0xc2):
            require(length>=7,'stimuli: invalid JPEG frame')
            h,w=struct.unpack('>HH',body[offset+5:offset+9]);size=(w,h)
        if marker==0xda:break  # entropy-coded scan follows; the end marker was checked above
        offset+=2+length
    require(size is not None,'stimuli: JPEG without frame')
    return size

def validate_images(bank,sources=None,*,photo=False):
    """photo=True: a photo-import revision — JPEG allowed, higher count/size/pixel totals."""
    max_total,max_count,max_pixels=(PHOTO_MAX_TOTAL,PHOTO_MAX_COUNT,PHOTO_MAX_PIXELS)if photo else(MAX_TOTAL,MAX_COUNT,16*1024*1024)
    total=0;count=0;pixels=0;known={s['source_id']:s for s in sources}if sources is not None else None
    for q in bank['questions']:
        images=q.get('stimuli',[])
        require(type(images)is list,'stimuli: array required')
        for s in images:
            validate_shape(s,IMAGE,'stimulus')
            x0,y0,x1,y1=s['crop']
            require(all(math.isfinite(x)for x in s['crop'])and 0<=x0<x1<=1 and 0<=y0<y1<=1,'stimuli: invalid crop')
            require(len(s['png_base64'])<=4*((MAX_IMAGE+2)//3),'stimuli: image too large')
            try:body=base64.b64decode(s['png_base64'],validate=True)
            except (ValueError,binascii.Error)as error:raise ValueError('stimuli: invalid PNG encoding')from error
            require(len(body)<=MAX_IMAGE,'stimuli: image too large')
            require(hashlib.sha256(body).hexdigest()==s['sha256'],'stimuli: content hash mismatch')
            if photo and body[:3]==JPEG:
                require(jpeg_size(body)==(s['width'],s['height']),'stimuli: dimensions mismatch')
                offset=len(body);types=[b'IHDR',b'IDAT',b'IEND']  # JPEG: markers checked by jpeg_size
            else:
                require(len(body)>=33 and body[:8]==b'\x89PNG\r\n\x1a\n'and body[12:16]==b'IHDR','stimuli: invalid PNG')
                require(struct.unpack('>II',body[16:24])==(s['width'],s['height']),'stimuli: dimensions mismatch')
                offset=8;types=[]
            while offset<len(body):
                require(offset+12<=len(body),'stimuli: truncated PNG chunk')
                size=struct.unpack('>I',body[offset:offset+4])[0];end=offset+12+size
                require(end<=len(body),'stimuli: truncated PNG')
                kind=body[offset+4:offset+8];data=body[offset+8:end-4]
                require(zlib.crc32(kind+data)&0xffffffff==struct.unpack('>I',body[end-4:end])[0],'stimuli: PNG checksum mismatch')
                types.append(kind);offset=end
                if kind==b'IEND':break
            require(types and types[0]==b'IHDR'and types[-1]==b'IEND'and b'IDAT'in types and offset==len(body),'stimuli: incomplete PNG')
            pixels+=s['width']*s['height']
            require(s['width']*s['height']<=4*1024*1024 and pixels<=max_pixels,'stimuli: pixel limit exceeded')
            if known is not None:
                src=known.get(s['source_id'])
                require(src is not None and src['sha256']==s['source_sha256']and type(src['page_count'])is int and s['page']<=src['page_count'],'stimuli: source/page mismatch')
            total+=len(body);count+=1
            require(total<=max_total and count<=max_count,'stimuli: total limit exceeded')
    return bank

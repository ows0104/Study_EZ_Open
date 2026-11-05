"""Bounded immutable PNG question stimuli. No paths, URLs or authored captions."""
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

def public_images(question):
    return [{'sha256':s['sha256'],'width':s['width'],'height':s['height'],
        'url':'data:image/png;base64,'+s['png_base64'],'alt':'문항 그림 '+str(i+1)}for i,s in enumerate(question.get('stimuli',[]))]

def validate_images(bank,sources=None):
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
            require(len(body)<=MAX_IMAGE and len(body)>=33 and body[:8]==b'\x89PNG\r\n\x1a\n'and body[12:16]==b'IHDR','stimuli: invalid PNG')
            require(hashlib.sha256(body).hexdigest()==s['sha256'],'stimuli: content hash mismatch')
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
            require(types[0]==b'IHDR'and types[-1]==b'IEND'and b'IDAT'in types and offset==len(body),'stimuli: incomplete PNG')
            pixels+=s['width']*s['height']
            require(s['width']*s['height']<=4*1024*1024 and pixels<=16*1024*1024,'stimuli: pixel limit exceeded')
            if known is not None:
                src=known.get(s['source_id'])
                require(src is not None and src['sha256']==s['source_sha256']and type(src['page_count'])is int and s['page']<=src['page_count'],'stimuli: source/page mismatch')
            total+=len(body);count+=1
            require(total<=MAX_TOTAL and count<=MAX_COUNT,'stimuli: total limit exceeded')
    return bank

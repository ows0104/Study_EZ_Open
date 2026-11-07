"""Original embedded image catalog with immutable provenance and page fallback."""
import hashlib
import json
from pathlib import Path
import fitz


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(packet, material):
    material = Path(material)
    entries = []
    for source in packet['sources']:
        path = Path(source['localPath'])
        if sha(path) != source['sha256']:
            raise ValueError('Figure source hash changed')
        if path.suffix.lower() != '.pdf':
            continue
        with fitz.open(path) as doc:
            for page in doc:
                bounds = page.rect
                for info in page.get_image_info(xrefs=True):
                    xref = info['xref']
                    x0, y0, x1, y1 = info['bbox']
                    # Keep transforms, masks, clipping and composites on the original page.
                    a, b, c, d, _, _ = info['transform']
                    if not xref or b or c or a <= 0 or d <= 0 or not (0 <= x0 < x1 <= bounds.width and 0 <= y0 < y1 <= bounds.height):
                        continue
                    if min(info['width'], info['height']) < 80:
                        continue
                    extracted = doc.extract_image(xref)
                    if extracted.get('smask', 0):
                        continue
                    pix = fitz.Pixmap(doc, xref)
                    if pix.alpha or pix.n > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    # Preserve originals; omit oversized candidates rather than silently degrade.
                    if max(pix.width, pix.height) > 4096 or pix.width * pix.height > 4 * 1024 * 1024:
                        continue
                    body = pix.tobytes('png')
                    if len(body) > 1024 * 1024:
                        continue
                    digest = hashlib.sha256(body).hexdigest()
                    name = 'figure-' + digest + '.png'
                    target = material / name
                    if target.exists() and target.read_bytes() != body:
                        raise ValueError('Figure cache changed')
                    target.write_bytes(body)
                    entries.append(dict(image_id=f"{source['id']}-p{page.number+1}-i{len(entries)+1}",
                        source_id=source['id'], source_sha256=source['sha256'], page=page.number+1,
                        crop=[x0/bounds.width,y0/bounds.height,x1/bounds.width,y1/bounds.height],
                        sha256=digest,width=pix.width,height=pix.height,path=name,method='embedded'))
    value={'policy':'original-figures/1','images':entries,
        'note':'Compare each image with the rendered page. Separate arrows/text are not embedded. Use page crop when needed.'}
    target=material/'figure-index.json'
    if target.exists() and json.loads(target.read_text(encoding='utf-8')) != value:
        raise ValueError('Existing figure catalog differs')
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    return value


def selected(spec, source, material):
    """Only read a host-generated, hash-bound image for an exact source placement."""
    catalog=json.loads((Path(material)/'figure-index.json').read_text(encoding='utf-8'))
    rows=[row for row in catalog['images'] if row['image_id']==spec['image_id']]
    if len(rows)!=1:
        raise ValueError('Unknown original image ID')
    row=rows[0]
    if (row['source_id']!=source['id'] or row['source_sha256']!=source['sha256'] or
        row['page']!=spec['page'] or row['crop']!=spec['crop']):
        raise ValueError('Original image placement differs')
    path=Path(material)/row['path']
    if path.name!='figure-'+row['sha256']+'.png' or sha(path)!=row['sha256']:
        raise ValueError('Original image bytes changed')
    return path.read_bytes(),row['width'],row['height']

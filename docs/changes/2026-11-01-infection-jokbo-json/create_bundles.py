"""Package the verified canonical data and a convenient GPT attachment export."""
from pathlib import Path
import hashlib,json,re,zipfile
import build_package as b

v=json.loads((b.HERE/'materials-verification.json').read_text(encoding='utf-8'))
assert v['status']=='passed' and v['manifest_sha256']==b.file_sha(b.OUT/'manifest.json')
assert json.loads((b.HERE/'visual-review.json').read_text(encoding='utf-8'))['status']=='passed'
catalog=json.loads((b.OUT/'catalog.json').read_text(encoding='utf-8'))
parent=b.OUT.parent
full_path=parent/'감염과 면역_2026_JSON_전체.zip'
gpt_path=parent/'감염과 면역_2026_GPT첨부용.zip'
assert not full_path.exists() and not gpt_path.exists()
bundle_records=[]

def build_zip(path,entries):
    temp=path.with_suffix('.partial')
    members=[]
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for name,source in entries:
            if isinstance(source,Path):
                archive.write(source,name);digest=b.file_sha(source);size=source.stat().st_size
            else:
                data=source.encode('utf-8') if isinstance(source,str) else source
                archive.writestr(name,data);digest=b.sha(data);size=len(data)
            members.append({'file':name,'bytes':size,'sha256':digest})
    temp.replace(path)
    record={'path':str(path),'bytes':path.stat().st_size,'sha256':b.file_sha(path),'members':members}
    print('BUNDLED',path.name,len(members),'files',round(path.stat().st_size/1048576,1),'MiB',flush=True)
    return record

full_entries=[('감염과 면역_2026_JSON/'+p.relative_to(b.OUT).as_posix(),p) for p in sorted(b.OUT.rglob('*')) if p.is_file()]
bundle_records.append(build_zip(full_path,full_entries))
gpt_entries=[]
gpt_root='감염과 면역_GPT첨부용/'
mapping=[]
for entry in catalog['sections']:
    title=re.sub(r'[\\/:*?"<>|]','_',entry['title'])
    folder=f'{entry["id"]}_{title}'
    content=(b.OUT/entry['markdown']).read_text(encoding='utf-8')
    content=content.replace('../gpt-images/','그림/').replace('gpt-images PNG','그림 폴더의 PNG')
    gpt_entries.append((gpt_root+folder+'/문항.md',content))
    image_names=[]
    for file in entry['image_files']:
        name='그림/'+Path(file).name
        gpt_entries.append((gpt_root+folder+'/'+name,b.OUT/file));image_names.append(name)
    listing=('이 폴더의 문항.md와 해당 문항의 그림 PNG를 같은 메시지에 첨부하세요.\n'
             '그림이 많으면 문항별로 나누어 첨부하세요. 원본 정답 연결 확인 표시는 유지되어 있습니다.\n\n'
             +'\n'.join(image_names)+'\n')
    gpt_entries.append((gpt_root+folder+'/첨부목록.txt',listing))
    for row in catalog['lectures']:
        if row['section_id']==entry['id']:
            lecture=row['lecture']
            mapping.append(f'{lecture["date"]} {lecture["slot"]}교시 | {lecture["title"]}\n'
                           f'  담당: {"·".join(lecture["professors"])}\n'
                           f'  자료 폴더: {folder}\n')
gpt_entries.append((gpt_root+'수업별_자료목록.txt','\n'.join(sorted(mapping))))
gpt_entries.append((gpt_root+'사용안내.txt',
    '원하는 수업은 수업별_자료목록.txt에서 찾으세요. 각 단원 폴더에 문항.md와 그림 폴더가 있습니다.\n'
    'ChatGPT 웹에는 문항.md와 실제 PNG를 함께 첨부합니다. ZIP이나 MD 링크만으로 그림이 전달된다고 가정하지 마세요.\n'
    '그림 여백의 문항/그림 ID로 텍스트와 연결합니다. 먼저 보이는 그림과 대응 문항을 확인하도록 요청하세요.\n'
    'JSON 기준 자료, 원본 PDF 및 전체 원문 대조 이미지는 별도 JSON 전체 묶음에 보관되어 있습니다.\n'
    '정답은 원본 표기 기준이며, 19개의 연결 확인 상태를 그대로 유지했습니다.\n'))
bundle_records.append(build_zip(gpt_path,gpt_entries))
b.save_json(b.HERE/'bundles.json',{'source_manifest_sha256':v['manifest_sha256'],'bundles':bundle_records})

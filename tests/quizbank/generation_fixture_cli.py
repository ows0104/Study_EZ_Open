"""Test-only child CLI. Production orchestration with a synthetic model adapter."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'contracts'))
import automation_fixture as f
from quizbank import connection_generate as generator
import json,shutil
import generation_v2_fixture as v2
from quizbank import connection_parallel as parallel

def independent(kind,context,material,seat,model):
    # Explicit test-only adapter: no provider call, actual file/receipt validation.
    work=seat/'work';work.mkdir();shutil.copytree(material,work/'material')
    generator.write(work/'input.json',context)
    generator.write(work/'acceptance.schema.json',parallel.schema(kind))
    (work/'task.md').write_text('Synthetic nonmedical fixture only')
    (work/'check_result.py').write_text('# Synthetic nonmedical fixture')
    generator.write(seat/'protected.json',{p.relative_to(work).as_posix():parallel.sha(p)for p in work.rglob('*')if p.is_file()})
    ref={'source_id':'S1','pages':[1],'locator':'Synthetic original'}
    if kind=='map':value={'schema_version':'concept-map-extract/2','title':'Synthetic','overview':'Synthetic A/B',
        'concepts':[{'concept_id':'C001','title':'A/B','core_facts':['Synthetic fact'],'source_refs':[ref]}],'relations':[],'notes':[]}
    elif kind=='point':value={'schema_version':'exam-point-extract/2','title':'Synthetic','points':[{'point_id':'P001','point':'Recall A/B','source_refs':[ref]}],'notes':[]}
    else:
        author=v2.author();value={k:author[k]for k in ('bank','visual_stimuli','clinical_conflicts')}
    generator.write(work/'result.json',value)
    provider={'text':json.dumps({'path':'result.json','sha256':parallel.sha(work/'result.json')}),'session_id':'synthetic-nonmedical','turns':1,'usage':{},'duration_ms':0,'models':{},'cost_usd':None}
    return value,provider

packet=json.loads(Path(sys.argv[sys.argv.index('--packet')+1]).read_text(encoding='utf-8'))
from studyez_contracts.roots.parallel import is_v2_source
generator.call_model=v2.model if is_v2_source(packet)else f.model
parallel.model_job=independent
if __name__=='__main__':raise SystemExit(generator.main())

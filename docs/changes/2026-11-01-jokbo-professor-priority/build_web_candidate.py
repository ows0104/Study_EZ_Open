"""Build only this change over deployed HEAD, preserving other uncommitted work."""
from pathlib import Path
import hashlib, io, json, shutil, subprocess, zipfile
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
OUT=ROOT/'output/releases/jokbo-professor-source-v2'
FILES=('web/src/lecture/reviewProfessor.ts','web/src/lecture/reviewPrompt.ts',
       'web/tests/review-professor.test.cjs','content/prompts/bank/bankPrompt.md')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

assert not OUT.exists(), 'Preserve a prepared source'
OUT.mkdir(parents=True)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert revision=='35663e610ed003182e05fddfd828e871336fc389'
data=subprocess.check_output(['git','archive','--format=zip','HEAD','web','content','bridge','platform'],cwd=ROOT)
with zipfile.ZipFile(io.BytesIO(data)) as z:
    for name in z.namelist():assert (OUT/name).resolve().is_relative_to(OUT.resolve())
    z.extractall(OUT)
for name in FILES:
    target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
# Use the existing installed dependencies; no installation or network access.
shutil.copytree(ROOT/'web/node_modules',OUT/'web/node_modules')
for name in ('.env','.env.local','.env.production','.env.production.local'):
    path=ROOT/'web'/name
    if path.is_file():shutil.copyfile(path,OUT/'web'/name)
subprocess.run(['node','--test','tests/review-professor.test.cjs','tests/bank-prompt-current.test.cjs'],cwd=OUT/'web',check=True)
subprocess.run(['npm.cmd','run','build'],cwd=OUT/'web',check=True)
artifact=ROOT/'web/dist';backup=ROOT/'web/dist-before-professor-candidate'
assert artifact.resolve().parent==backup.resolve().parent==(ROOT/'web').resolve()
assert artifact.resolve().is_relative_to(ROOT.resolve()) and backup.resolve().is_relative_to(ROOT.resolve())
assert not backup.exists()
if artifact.exists():artifact.rename(backup)
shutil.copytree(OUT/'web/dist',artifact)
manifest={'base_revision':revision,'overlay_files':{name:digest(ROOT/name) for name in FILES},
          'isolated_source':str(OUT),'artifact':str(artifact),'other_uncommitted_changes_included':False}
(HERE/'web-source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Built isolated candidate from deployed HEAD plus the four reviewed files.')

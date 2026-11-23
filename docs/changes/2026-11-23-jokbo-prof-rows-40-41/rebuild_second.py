"""감염과 면역 2차 족보 첨부 5개를 올해 실제 담당 교수 기준으로 다시 만든다(사용자 2026-11-23 「응, 5개 고쳐줘」).

11-01 export는 2차 강의의 올해 교수를 원본 책 119쪽 표의 2026 칸(김민정·양민석·장윤석·김세훈·박흥우)으로 잡았다.
11-05 시간표와 운영 강의는 박준원·장윤석·강성윤·양민석·김세훈이다. 과거 연도 칸은 작년 필기 파일명과 맞으므로 그대로 쓴다.
호산구성 질환(S64) 표의 「박홍우」는 오타로 보고 「박흥우」로 고친다(같은 줄 다른 칸과 다른 줄 모두 박흥우,
docs/changes/2026-11-23-infection-jokbo-2nd/build_source.py NAME_FIX와 같다).

- 읽기만: 관리 JSON 원본, 운영 강의·자산 목록(어느 섹션이 붙어 있는지).
- 새로 씀: output/materials/감염과 면역_2026_JSON_교수표정정/sections/S64.json(오타만),
  output/pdf/감염과 면역_2026_교수우선_v3_2차올해교수/, 이 폴더의 rebuild-second-plan.json.

    1) <메인>/server/.venv/Scripts/python.exe rebuild_second.py <메인> --snapshot   운영 강의·첨부를 live-snapshot.json에(읽기만)
    2) python rebuild_second.py <메인>                                              PDF 만들기(pymupdf)
"""
from __future__ import annotations

import copy, hashlib, importlib.util, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = Path(sys.argv[1]).resolve()
SNAPSHOT = HERE / "live-snapshot.json"

PACKAGE = MAIN / "output/materials/감염과 면역_2026_JSON"
FIXED = MAIN / "output/materials/감염과 면역_2026_JSON_교수표정정"
OUT = MAIN / "output/pdf/감염과 면역_2026_교수우선_v3_2차올해교수"
OLD = MAIN / "output/pdf/감염과 면역_2026_교수우선_v2"
SUBJECT = "감염과 면역"
# run_id → 올해 담당(운영 강의·2026 시간표). 실행 때 운영 값과 같은지 확인한다.
CURRENT = {"261124_01": ["박준원"], "261125_02": ["장윤석"], "261126_01": ["강성윤"],
           "261126_03": ["양민석"], "261126_05": ["김세훈"]}
NAME_FIX = {"박홍우": "박흥우"}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))


def fix_names(section):
    s = copy.deepcopy(section)
    fixed = []
    for y, names in s["professors_by_year"].items():
        new = list(dict.fromkeys(NAME_FIX.get(n, n) for n in names))
        if new != names: fixed.append(y)
        s["professors_by_year"][y] = new
    for q in s["questions"]:
        q["professors_from_source_table"] = list(dict.fromkeys(NAME_FIX.get(n, n) for n in q["professors_from_source_table"]))
    if fixed:
        s["professor_name_fix"] = {"date": "2026-11-23", "map": NAME_FIX, "years": fixed,
                                   "source_section_sha256": sha(PACKAGE / "sections" / f"{s['id']}.json"),
                                   "reason": "같은 줄 21·20열과 60·63·66번 줄은 모두 박흥우. 2차 족보 풀이 자료(build_source.py NAME_FIX)와 같은 보정"}
    return s, fixed


def snapshot():
    sys.path.insert(0, str(MAIN)); sys.path.insert(0, str(MAIN / "server")); os.chdir(MAIN / "server")
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import Asset, Lecture
    with SessionLocal() as db:
        lectures = {l.run_id: {"title": l.title, "professors": l.professors}
                    for l in db.scalars(select(Lecture).where(Lecture.subject == SUBJECT, Lecture.run_id.in_(CURRENT)))}
        assets = {a.run_id: {"filename": a.filename, "object_key": a.object_key}
                  for a in db.scalars(select(Asset).where(Asset.subject == SUBJECT, Asset.kind == "jokbo", Asset.run_id.in_(CURRENT)))}
    SNAPSHOT.write_text(json.dumps({"lectures": lectures, "assets": assets}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SNAPSHOT", len(lectures), len(assets))


class Row(dict):
    __getattr__ = dict.__getitem__


def main():
    import pymupdf as f
    catalog = read(PACKAGE / "catalog.json")
    source_path = PACKAGE / catalog["source"]["file"]
    assert sha(source_path) == catalog["source"]["sha256"]
    snap = read(SNAPSHOT)
    lectures = {k: Row(v) for k, v in snap["lectures"].items()}
    assets = {k: Row(v) for k, v in snap["assets"].items()}
    spec = importlib.util.spec_from_file_location("build_materials", MAIN / "docs/changes/2026-11-01-jokbo-professor-priority/build_materials.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder); builder.OUT = OUT
    assert not OUT.exists(), "이전 export를 덮어쓰지 않는다"
    OUT.mkdir(parents=True)
    source = f.open(source_path)
    files, rows = {}, []
    for run_id, current in CURRENT.items():
        assert lectures[run_id].professors == current, (run_id, lectures[run_id].professors)
        live = assets[run_id]
        sid = re.match(r"2026-(S\d+)-족보-", live.filename).group(1)
        section, fixed = fix_names(read(PACKAGE / "sections" / f"{sid}.json"))
        if fixed:
            target = FIXED / "sections" / f"{sid}.json"
            assert not target.exists(); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(section, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = builder.make(section, current, "timetable", source)
        before = OLD / live.filename
        same = sum(q["priority"] for q in result["questions"])
        files[run_id] = {**result, "priorityQuestions": same, "nameFixYears": fixed,
                         "replaces": {"filename": live.filename, "objectKey": live.object_key,
                                      "archive": str(before), "sha256": sha(before)}}
        rows.append({"run_id": run_id, "section_id": sid, "path": result["path"], "sha256": result["sha256"]})
        print("BUILT", run_id, sid, lectures[run_id].title, "|", live.filename, "→", Path(result["path"]).name,
              f"| same {same}/{len(result['questions'])}", flush=True)
    (HERE / "rebuild-second-plan.json").write_text(json.dumps(
        {"source": {"path": str(source_path), "sha256": catalog["source"]["sha256"]}, "files": files, "lectures": rows},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    snapshot() if "--snapshot" in sys.argv else main()

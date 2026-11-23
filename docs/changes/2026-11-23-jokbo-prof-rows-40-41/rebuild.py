"""감염과 면역 2026 족보: 교수님 목록 40·41번 줄의 2020~2025 교수 뒤바뀜을 정정해 두 강의 PDF만 새로 만든다.

원본 표(원본 PDF 2쪽)는 40 「레오바이러스, 코로나바이러스 노로바이러스」 줄에 감염학 교수(최평균·김의석·강창경·박완범)를,
41 「방어기전 손상환자의 감염」 줄에 조남혁을 2025~2020 칸에 적었다. 2026 칸은 맞다(40 조남혁, 41 최평균).
과목 칸도 40이 「감염」, 41이 「미생」으로 수업 제목과 어긋난다. 근거는 EVIDENCE에 적는다.

- 읽기만: output/materials/감염과 면역_2026_JSON(관리 JSON), 이전 export 계획(upload-plan.json).
- 새로 씀(덮어쓰지 않음): output/materials/감염과 면역_2026_JSON_교수표정정/, output/pdf/감염과 면역_2026_교수우선_v3_교수표정정/,
  이 폴더의 rebuild-plan.json.
- 운영 첨부 교체·족보 풀이 자료·Main-Quiz 재계산은 하지 않는다(별도 승인).

    python docs/changes/2026-11-23-jokbo-prof-rows-40-41/rebuild.py <메인 체크아웃 경로>
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pymupdf as f

HERE = Path(__file__).resolve().parent
MAIN = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE.parents[2]
PACKAGE = MAIN / "output/materials/감염과 면역_2026_JSON"
FIXED = MAIN / "output/materials/감염과 면역_2026_JSON_교수표정정"
OUT = MAIN / "output/pdf/감염과 면역_2026_교수우선_v3_교수표정정"
OLD_PLAN = MAIN / "docs/changes/2026-11-01-jokbo-professor-priority/upload-plan.json"
YEARS = ("25", "24", "23", "22", "21", "20")

# 원본 표에 적힌 그대로(정정 전). 다르면 원본이나 관리 JSON이 바뀐 것이므로 멈춘다.
TABLE_AS_PRINTED = {
    "S40": {"26": ["조남혁"], "25": ["최평균"], "24": ["김의석"], "23": ["김의석"],
            "22": ["강창경", "김의석", "박완범"], "21": ["강창경", "김의석", "박완범"], "20": ["김의석", "강창경"]},
    "S41": {"26": ["최평균"], **{y: ["조남혁"] for y in YEARS}},
}
EVIDENCE = [
    {"file": "감염과 면역 족보_2026_원본.pdf", "pages": [2, 3],
     "fact": "교수님 목록 40번 줄은 과목 「감염」에 감염학 교수, 41번 줄은 과목 「미생」에 조남혁. 수업 제목(레오·코로나·노로 = 미생물학, "
             "방어기전 손상환자 = 감염학, 2026 시간표 기준)과 과목·교수가 어긋난다. 3쪽 안내는 40번 강의의 순서가 바뀌었다고 적는다."},
    {"file": "[261118_05]레오바이러스,코로나바이러스,노로바이러스(조남혁)_채시원v1.pdf",
     "sha256": "b4936cf84701747b84806e2a8a68d23ea5fae10051b6dc8d444f5ce98fbb654a", "pages": [1],
     "fact": "「본 강의는 2017년부터 조남혁 교수님께서 맡아주셨고」"},
    {"file": "[261118_02] 방어기전손상환자의 감염(최평균)_좌예원_v1.pdf",
     "sha256": "7e88892f1b3707c51b97743dfa418259eee74bbbcb47891f16ecb63a31ddc1cd", "pages": [8],
     "fact": "「2025년 출제 [최평균 교수님]」 족보 스탬프"},
    {"source": "사용자 2026-11-23", "fact": "「이 강의는 2017년부터 조남혁 교수님이 담당하셨는데?」"},
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data) -> None:
    assert not path.exists(), f"덮어쓰지 않는다: {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def corrected_sections() -> dict[str, dict]:
    sections = {sid: read(PACKAGE / "sections" / f"{sid}.json") for sid in ("S40", "S41")}
    for sid, section in sections.items():
        assert section["professors_by_year"] == TABLE_AS_PRINTED[sid], (sid, section["professors_by_year"])
    fixed = {sid: copy.deepcopy(s) for sid, s in sections.items()}
    for sid, other in (("S40", "S41"), ("S41", "S40")):
        by_year = fixed[sid]["professors_by_year"]
        for y in YEARS:
            by_year[y] = list(sections[other]["professors_by_year"][y])
        for q in fixed[sid]["questions"]:
            year = str(q["year"])
            if year[:2] == "20" and year[2:4] in YEARS:
                q["professors_from_source_table"] = list(by_year[year[2:4]])
        fixed[sid]["professor_table_correction"] = {
            "date": "2026-11-23", "years": ["20" + y for y in YEARS], "swapped_with": other,
            "table_as_printed": TABLE_AS_PRINTED[sid], "evidence": EVIDENCE,
            "source_section_sha256": sha(PACKAGE / "sections" / f"{sid}.json"),
        }
        # 문항 내용·정답·원본 영역은 그대로여야 한다.
        strip = lambda qs: [{k: v for k, v in q.items() if k != "professors_from_source_table"} for q in qs]
        assert strip(fixed[sid]["questions"]) == strip(sections[sid]["questions"])
    return fixed


def load_builder():
    spec = importlib.util.spec_from_file_location("build_materials", MAIN / "docs/changes/2026-11-01-jokbo-professor-priority/build_materials.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    return module


def main() -> None:
    catalog = read(PACKAGE / "catalog.json")
    source_path = PACKAGE / catalog["source"]["file"]
    assert sha(source_path) == catalog["source"]["sha256"]
    old = read(OLD_PLAN)
    fixed = corrected_sections()
    assert not OUT.exists(), "이전 export를 덮어쓰지 않는다"
    OUT.mkdir(parents=True)
    for sid, section in fixed.items():
        write(FIXED / "sections" / f"{sid}.json", section)
    builder = load_builder()
    source = f.open(source_path)
    files, lectures = {}, []
    for lecture in old["lectures"]:
        if lecture["section_id"] not in fixed:
            continue
        before = old["files"][lecture["file_key"]]
        current = before["current_professors"]
        result = builder.make(fixed[lecture["section_id"]], current, before["professor_basis"], source)
        same = [q for q in result["questions"] if q["priority"]]
        files[lecture["file_key"]] = {**result, "replaces": {"path": before["path"], "sha256": before["sha256"],
                                                             "priorityQuestions": sum(q["priority"] for q in before["questions"])},
                                      "priorityQuestions": len(same)}
        lectures.append({**lecture, "path": result["path"], "sha256": result["sha256"]})
        print("BUILT", lecture["run_id"], lecture["section_id"], Path(result["path"]).name, result["pages"], "pages,",
              len(same), "/", len(result["questions"]), "same-professor", flush=True)
    write(HERE / "rebuild-plan.json", {"source": {"path": str(source_path), "sha256": catalog["source"]["sha256"]},
                                       "inputs": {str(PACKAGE / "sections" / f"{s}.json"): sha(PACKAGE / "sections" / f"{s}.json") for s in fixed},
                                       "fixedSections": {s: sha(FIXED / "sections" / f"{s}.json") for s in fixed},
                                       "previousPlan": {"path": str(OLD_PLAN), "sha256": sha(OLD_PLAN)},
                                       "files": files, "lectures": lectures})


if __name__ == "__main__":
    main()

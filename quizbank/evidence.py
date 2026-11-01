"""최종 문항을 보존한 채 핵심 근거와 실제 족보 지면을 덧붙인다."""
import json
import time
from pathlib import Path

from studyez_contracts.bank.slide_focus import all_selected_pages
from . import jokbo_pages, slide_focus, slides, evidence_sources, exam_focus
from .session import SessionError


def enrich(pdf: Path, out: Path, run_id: str, *, jokbo: Path | None = None, model: str | None = None) -> dict:
    started = time.monotonic()
    timings = {}
    def read(name):
        return json.loads((out / name).read_text(encoding="utf-8"))

    def write(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    bank, validation, result = read("bank.json"), read("validation.json"), read("result.json")
    related = {}
    try:
        authored_name = next((name for name in ("authored-evidence.json", "organize/authored-evidence.json")
                              if (out / name).is_file()), None)
        authored = read(authored_name) if authored_name else None
        related = evidence_sources.discover(pdf)
        focus, usage = slide_focus.select(bank, pdf, out / "slide-focus", model=model, authored=authored,
            related=related, source_cache=Path(__file__).resolve().parents[1] / "runs/_materials/evidence-sources", jokbo=jokbo)
        timings['selectionSeconds'] = round(time.monotonic() - started, 2)
        print(f"  웹 근거 재사용 {focus.get('authoredCount', 0)}문항 · 추가 지면 확인 {focus.get('reselectedCount', 0)}건", flush=True)
        focus["sourceFilename"] = pdf.name
        validation["slideFocus"] = focus
        result["slideFocus"] = {mode: sum(q["base"]["mode"] == mode for q in focus["questions"].values())
                                for mode in ("single", "linked", "unresolved")}
        with (out / "usage.jsonl").open("a", encoding="utf-8") as log:
            for entry in usage:
                log.write(json.dumps({"step": "문제·정답 핵심 근거 지면 선택", "t": int(time.time()), **entry}) + "\n")
    except (SessionError, ValueError, OSError) as cause:
        focus = {"version": 2, "questions": {}, "error": str(cause)}
        validation["slideFocus"] = focus
        result["slideFocusError"] = str(cause)
    phase = time.monotonic()
    references, images = jokbo_pages.connect(bank, jokbo, out / "slides", run_id)
    timings['jokboMappingSeconds'] = round(time.monotonic() - phase, 2)
    validation["jokboPages"] = references
    phase = time.monotonic()
    try:
        resolution, exam_usage = exam_focus.resolve(bank, focus, references, {'self': pdf, **related}, out, run_id, model)
        validation['evidenceResolution'] = resolution
        with (out / 'usage.jsonl').open('a', encoding='utf-8') as log:
            for entry in exam_usage:
                log.write(json.dumps({'step': '족보 핵심 지면 선택', 't': int(time.time()), **entry}) + '\n')
    except (SessionError, ValueError, OSError) as cause:
        validation['evidenceResolution'] = {'version': 1, 'questions': {}, 'error': str(cause)}
        result['evidenceResolutionError'] = str(cause)
    timings['examResolutionSeconds'] = round(time.monotonic() - phase, 2)
    pages = read("pages.json") if (out / "pages.json").is_file() else slides.cited_pages(bank, "S1")
    for question in bank["questions"]:
        qid = question["question_id"]
        pages[qid] = sorted(set(pages.get(qid, [])) | all_selected_pages(focus, qid))
    phase = time.monotonic()
    _, missing = slides.render(pdf, {page for refs in pages.values() for page in refs}, out / "slides", run_id)
    evidence_sources.render_selected(focus, related, out / "slides", run_id)
    result["slides"] = len(list((out / "slides").glob("*.png")))
    result["jokboSlides"] = len(images)
    result["missing_pages"] = missing
    timings['renderSeconds'] = round(time.monotonic() - phase, 2)
    timings['totalSeconds'] = round(time.monotonic() - started, 2)
    result['evidenceTimings'] = timings
    write('evidence-timings.json', timings)
    write("validation.json", validation)
    write("pages.json", pages)
    write("result.json", result)
    return result

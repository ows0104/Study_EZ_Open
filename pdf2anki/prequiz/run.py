"""예습 덱 하나를 명령 한 줄로 굽는다.

    python -m pdf2anki.prequiz.run "<작년 필기 PDF>" --note <URL 또는 파일>

복습 쪽 `run.py` 와 뼈대는 같다 — 산출물이 있는 단계는 건너뛰므로 끊겨도 같은 명령으로
이어진다. 다른 것은 셋이다.

**① 입력이 작년 자료다.** 예습 시점에 올해 필기는 존재하지 않는다. 그래서 덱 이름을
정할 때 문제가 하나 생긴다 — 덱은 **올해 강의**에 붙어야 하는데 파일은 작년 것이다.
파일 제목이 해마다 조금씩 달라서(29강 중 20강만 정확히 일치) 자동으로는 못 맞춘다.
그래서 작년 제목을 기본으로 쓰고 `--deck-title` 로 덮게 해 두었다.

**② 전략 판정이 없다.** 복습은 '이번 시험의 출제자가 누구의 강조점을 물을 것인가'로
세 갈래가 갈렸다. 예습에는 그 축이 없다 — 꼭 알아야 할 의학 지식은 출제자와 무관하다.
교수 교체는 `reason=repeated` 를 쓸 수 있는지만 가른다.

**③ 재현 검사가 선택이다.** 20~30장이라 싸지만, 예습은 강의 전날 급하게 도는 일이
잦다. 기본으로 돌리되 `--skip-reproduce` 로 건너뛸 수 있고 덱은 그래도 나온다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .. import ledger
from ..build import DEFECT_REASONS
from ..pack import find_jokbo, lecture_of
from ..run import Failed, lecture_id_of
from ..session import SessionError, run_agent
from .assemble import professor_line
from .schema import MAX_CARDS, MIN_CARDS

PY = sys.executable
CONFIG = "prequiz.config.json"
PROMPTS = Path(__file__).parent / "prompts"


def deck_of(lecture: str, subject: str) -> str:
    """`<과목>::<강의명>::예습`. 복습 덱의 `::강의록`·`::기출` 과 형제로 선다.

    강의명은 `--lecture` 로 주고, 안 주면 `pack.lecture_of` — 파일제목 원문이다.
    다만 여기서 파일명은 **작년 것**이다. 복습 덱과 한 노드에 세우려면 양쪽에
    `--lecture` 로 같은 값을 줘야 한다.
    """
    name = lecture.replace("::", "-")
    return f"{subject}::{name}::예습" if subject else f"{name}::예습"


# ── 예습 설명본 ────────────────────────────────────────────────────
class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.out.append(data.strip())


# ChatGPT 공유 링크 같은 최신 Next.js(App Router) 페이지는 본문을 DOM 이 아니라
# `<script>` 안 RSC 페이로드에 담는다. 그 안에서 JSON 이 한 겹 이스케이프돼 있어
# `_Text` 로는 24자밖에 못 건진다(실제로 그랬다). 페이로드가 문자열을 인터닝해 두어
# 구조를 제대로 파싱하려면 부서지기 쉬우므로, **긴 산문 덩어리만 주워 온다.**
#
# 정확한 복원이 목적이 아니다. 모델에게 읽힐 글을 건지는 것이 목적이라
# 순서가 조금 흐트러지거나 UI 문구가 섞여도 쓸 수 있다.
RSC_MIN_CHARS = 60          # 이보다 짧은 문자열은 UI 라벨·키 이름이다
RSC_MIN_HANGUL = 5
RE_QUOTED = re.compile(r'"([^"]{%d,})"' % RSC_MIN_CHARS)
RE_HANGUL = re.compile(r"[가-힣]")
# 인용 표식은 사설 사용 영역(PUA) 문자로 감싸여 있다. **문자만 지운다** —
# 두 표식 사이를 걸치는 정규식으로 지우면 그 사이의 본문까지 사라진다
# (실제로 15,475자가 4,520자로 줄었다).
RE_PUA = re.compile(r"[\ue000-\uf8ff]")
RE_CITE_TOKEN = re.compile(r"(?:filecite|turn\d+file\d+|L\d+-L\d+)")


def from_rsc(body: str) -> str:
    """스크립트 페이로드에서 긴 한글 산문만 순서대로 주워 잇는다.

    페이로드는 문자열을 인터닝해 두어 구조를 제대로 파싱하려면 부서지기 쉽다.
    정확한 복원이 목적이 아니라 **모델에게 읽힐 글을 건지는 것**이 목적이므로,
    따옴표 사이의 긴 덩어리 중 한글이 충분한 것만 순서대로 줍는다.
    """
    flat = body.replace('\\"', '"')          # HTML 안 JS 문자열 한 겹
    out, seen = [], set()
    for m in RE_QUOTED.finditer(flat):
        t = m.group(1)
        try:
            t = json.loads('"' + t + '"')   # \n · \\ · \uXXXX 를 푼다
        except ValueError:
            continue
        # **이스케이프가 두 겹이다.** RSC 페이로드가 JSON 을 JSON 안에 담아서,
        # 한 번 풀면 줄바꿈이 아직 문자 그대로(`\` + `n`)인 채로 남는다.
        # 한 번 더 풀어 실제 줄바꿈으로 만든다 — 안 하면 모델이 한 줄짜리 글을 읽는다.
        if "\\n" in t:
            try:
                t = json.loads('"' + t.replace('"', '\\"') + '"')
            except ValueError:
                t = t.replace("\\n", "\n")
        if len(RE_HANGUL.findall(t)) < RSC_MIN_HANGUL or t in seen:
            continue
        seen.add(t)
        out.append(RE_CITE_TOKEN.sub("", RE_PUA.sub("", t)).strip())
    return "\n\n".join(out)


def fetch_note(src: str, dst: Path) -> Path:
    """예습 설명본을 한 번 받아 굳힌다.

    링크가 죽어도 재실행이 되어야 하고, 무엇을 근거로 만든 덱인지 나중에 되짚을 수
    있어야 한다. 그래서 URL 이면 받아서 파일로 남기고, 이후 단계는 그 파일만 본다.

    로그인이 필요하거나 JS 로 그리는 페이지는 이 방법으로 못 가져온다.
    그럴 때는 내용을 `.md` 로 저장해 그 경로를 주면 된다.
    """
    if not re.match(r"https?://", src):
        p = Path(src)
        if not p.exists():
            raise Failed(f"예습 설명본을 찾지 못했다: {p}")
        shutil.copy2(p, dst)
        return dst
    try:
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            charset = r.headers.get_content_charset() or "utf-8"
        body = raw.decode(charset, errors="replace")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Failed(f"예습 설명본을 받지 못했다 ({e}). "
                     f"내용을 .md 로 저장해 --note <경로> 로 줘라")
    p = _Text()
    p.feed(body)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(p.out)).strip()
    how = "DOM"
    if len(text) < 400:
        # DOM 에 글이 없으면 스크립트 페이로드를 뒤진다 (ChatGPT 공유 링크 등)
        alt = from_rsc(body)
        if len(alt) > len(text):
            text, how = re.sub(r"\n{3,}", "\n\n", alt).strip(), "스크립트 페이로드"
    if len(text) < 400:
        raise Failed(f"받아온 글이 너무 짧다({len(text)}자). 로그인이 필요한 페이지이거나 "
                     f"형식이 바뀌었을 수 있다. 내용을 .md 로 저장해 --note <경로> 로 줘라")
    dst.write_text(f"<!-- 출처: {src} ({how}) -->\n\n{text}\n", encoding="utf-8")
    return dst


# ── must_know 검토 ────────────────────────────────────────────────
def render_must(must: dict) -> str:
    from .schema import REASON_WHY
    lines = ["# 반드시 알아야 할 것", ""]
    total = 0
    for i, it in enumerate(must.get("items", []), 1):
        n = it.get("cards", 1)
        total += n
        lines.append(f"**{i}. {it['item']}**  ·  `{it['reason']}` · 카드 {n}장"
                     + (f" · Slide {', '.join(str(s) for s in it['slides'])}"
                        if it.get("slides") else ""))
        lines.append(f"   └ {it['why']}")
        if it.get("jokbo_refs"):
            lines.append(f"   └ 기출 {', '.join(it['jokbo_refs'])}")
        lines.append("")
    lines.append(f"— 항목 {len(must.get('items', []))}개 · 카드 합계 **{total}장** "
                 f"(계약 {MIN_CARDS}~{MAX_CARDS})")
    rej = must.get("rejected_candidates") or []
    if rej:
        lines += ["", "## 예습에 넣지 않은 것", ""]
        for r in rej:
            lines.append(f"- {r['candidate']}  `{r['reason']}`")
        exam = [r for r in rej if r["reason"] == "exam_only"]
        if exam:
            lines += ["", f"> `exam_only` {len(exam)}건은 복습 덱이 가져갈 몫이다."]
    lines += ["", "## 이유 코드", ""]
    lines += [f"- `{k}` — {v}" for k, v in REASON_WHY.items()]
    return "\n".join(lines) + "\n"


class Runner:
    def __init__(self, out: Path, args):
        self.out, self.args = out, args
        self.cost, self.t0 = 0.0, time.time()
        self.sid: str | None = None
        self.run = ledger.run_id()
        os.environ[ledger.ENV_RUN] = self.run
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        self.stayed, self.prof = True, "미상"
        self.slice_path = None
        self.contract_broken = False

    def made(self, produces: str | None) -> bool:
        if not produces:
            return False
        if "*" in produces:
            return any(self.out.glob(produces))
        return (self.out / produces).exists()

    def prompt_path(self, stage: str) -> Path:
        one = self.out / f"prompt.{stage}.md"
        if one.exists():
            return one
        parts = sorted(self.out.glob(f"prompt.{stage}.1of*.md"))
        if parts:
            return parts[0]
        raise Failed(f"prompt.{stage}.md 가 없다")

    def step(self, name: str, produces: str | None, fn):
        if produces and self.made(produces) and not self.args.force:
            print(f"[건너뜀] {name}  ({produces} 이미 있음)", flush=True)
            return
        print(f"\n── {name}", flush=True)
        n0 = len(ledger.read(self.out))
        t = time.time()
        self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
        fn()
        if len(ledger.read(self.out)) == n0:
            ledger.append(self.out, name, seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions)
        if produces and not self.made(produces):
            raise Failed(f"{name}: {produces} 가 생기지 않았다")

    def sh(self, *argv: str, ok: tuple = (0,)) -> int:
        """`ok` 에 없는 종료코드면 멈춘다.

        `validate` 는 계약 위반에 2 를 낸다. 그것까지 죽으면 **한 줄 실행이 깨진다** —
        사람이 `--allow-size` 를 붙여 다시 불러야 하기 때문이다. 2 는 받아 두고
        수선 루프가 처리한다.
        """
        r = subprocess.run([PY, "-m", *argv], cwd=Path.cwd(),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                ledger.ENV_RUN: self.run})
        if r.returncode not in ok:
            raise Failed(f"명령 실패: {' '.join(argv)}")
        return r.returncode

    def agent(self, prompt: str, label: str, resume: bool = False):
        if self.args.hint:
            prompt += ("\n\n## 이 강의에 대한 사용자 지시 (프롬프트보다 우선한다)\n\n"
                       + self.args.hint + "\n")
        res = run_agent(prompt, cwd=Path.cwd(), model=self.args.model,
                        timeout=self.args.timeout, label=label,
                        resume=self.sid if resume else None)
        self.cost += res.get("cost_usd") or 0.0
        self.pend_cost += res.get("cost_usd") or 0.0
        self.pend_sessions += 1
        ledger.add(self.pend_usage, res.get("usage"))
        if res.get("session_id"):
            self.sid = res["session_id"]
        for line in (res.get("text") or "").strip().splitlines()[-6:]:
            print(f"   {line[:110]}", flush=True)
        return res

    # ── 단계 ──────────────────────────────────────────────────
    def prep(self):
        if not self.args.pdf:
            raise Failed("prep.json 이 없는데 PDF 경로도 모른다")
        self.sh("pdf2anki.prep", str(self.args.pdf), "-o", str(self.out))

    def note(self):
        if not self.args.note:
            print("   예습 설명본 없음 — 강의록·필기·기출만으로 간다")
            return
        dst = fetch_note(self.args.note, self.out / "note.md")
        print(f"   예습 설명본 {dst.stat().st_size:,}바이트 → {dst.name}")

    def read_professor(self):
        prep = json.loads((self.out / "prep.json").read_text(encoding="utf-8"))
        jd = Path(self.args.jokbo_dir)
        if self.args.jokbo:
            slice_path = Path(self.args.jokbo)
        elif (jd / "index.json").exists():
            slice_path, score, _ = find_jokbo(prep, jd)
            if score < 0.25:
                slice_path = None
        else:
            slice_path = None
        self.slice_path = slice_path
        if slice_path:
            stats = json.loads(slice_path.read_text(encoding="utf-8")).get("stats", {})
            self.stayed, self.prof = professor_line(stats)
        print(f"   담당 교수 {'유임' if self.stayed else '교체'} ({self.prof}) → "
              f"reason=repeated {'사용 가능' if self.stayed else '금지'}")

    def schema(self):
        self.sh("pdf2anki.prequiz.schema", "-o", self.args.schema_dir)

    def assemble(self):
        argv = ["pdf2anki.prequiz.assemble", str(self.out),
                "--jokbo-dir", self.args.jokbo_dir, "--schema-dir", self.args.schema_dir]
        if self.args.jokbo:
            argv += ["--jokbo", self.args.jokbo]
        self.sh(*argv)

    def must(self):
        self.agent(f'Read("{self.prompt_path("must").resolve().as_posix()}") 부터 시작해라.',
                   "① 반드시 알아야 할 것")

    def approve(self):
        must = json.loads((self.out / "must_know.json").read_text(encoding="utf-8"))
        md = render_must(must)
        (self.out / "must_know.review.md").write_text(md, encoding="utf-8")
        print(md)
        if self.args.stop_at_review:
            print("\n검토하고 이어서 돌려라:", flush=True)
            print(f"   python -m pdf2anki.prequiz.run --resume {self.out.as_posix()}")
            raise SystemExit(0)
        shutil.copy2(self.out / "must_know.json", self.out / "must_know.approved.json")

    def cards(self):
        self.agent(f'Read("{self.prompt_path("cards").resolve().as_posix()}") 부터 시작해라.',
                   "② 카드", resume=True)

    def validate(self):
        argv = ["pdf2anki.prequiz.validate", str(self.out / "items.raw.json"),
                "--prep", str(self.out / "prep.json"),
                "--must", str(self.out / "must_know.approved.json")]
        if self.slice_path:
            argv += ["--jokbo", str(self.slice_path)]
        if not self.stayed:
            argv += ["--professor-changed"]
        self.contract_broken = self.sh(*argv, ok=(0, 2)) == 2

    def reproduce(self, only: list[str] | None = None):
        """only 를 주면 그 카드만 다시 풀고 채점한다. 나머지 결과는 그대로 살아 있다."""
        if self.args.skip_reproduce:
            print("   --skip-reproduce")
            return
        if not only:
            for f in ("reproduce.answers.json", "reproduce.grades.json",
                      "items.reproduced.json"):
                (self.out / f).unlink(missing_ok=True)
        argv = ["pdf2anki.reproduce", "check", str(self.out), "--jobs", str(self.args.jobs)]
        if only:
            argv += ["--only", ",".join(only)]
        if self.args.model:
            argv += ["--model", self.args.model]
        self.sh(*argv)

    # ── 수선 ───────────────────────────────────────────────────
    def defects(self) -> list[dict]:
        """재현 검사가 **카드 결함**으로 가른 것만. lecture_specific·genuinely_wrong 은 아니다."""
        f = self.out / "items.reproduced.json"
        if not f.exists():
            return []
        cards = json.loads(f.read_text(encoding="utf-8"))["cards"]
        return [c for c in cards
                if (c.get("reproduce") or {}).get("reason") in DEFECT_REASONS]

    def violations(self) -> list[str]:
        f = self.out / "suspects.json"
        if not f.exists():
            return []
        return json.loads(f.read_text(encoding="utf-8")).get("contract_violations", [])

    def repair(self):
        """결함 카드와 계약 위반을 다시 쓰게 하고 검사를 다시 돈다. 줄지 않으면 그만둔다."""
        for rnd in range(1, self.args.repair_rounds + 1):
            bad, viol = self.defects(), self.violations()
            if not bad and not viol:
                return
            print(f"\n── 수선 {rnd}/{self.args.repair_rounds}  "
                  f"(결함 {len(bad)}장 · 계약 위반 {len(viol)}건)", flush=True)
            t = time.time()
            self.pend_cost, self.pend_usage, self.pend_sessions = 0.0, {}, 0
            raw = (self.out / "items.raw.json").resolve().as_posix()
            body = []
            for v in viol:
                body.append(f"### [계약] {v}")
            for c in bad:
                r = c["reproduce"]
                body.append(f"### [{r['reason']}] {c['q']}\n"
                            f"- 원래 답: {c['a']}\n"
                            f"- 질문만 보고 다시 푼 답: "
                            f"{r.get('reproduced_answer') or '(풀 수 없다고 답함)'}\n"
                            f"- 채점 메모: {r.get('note') or ''}")
            task = (PROMPTS / "repair.md").read_text(encoding="utf-8").replace("{raw}", raw)
            self.agent(task + "\n\n" + "\n\n".join(body), f"수선{rnd}",
                       resume=bool(self.sid))
            ledger.append(self.out, "수선", seconds=time.time() - t, cost=self.pend_cost,
                          usage=self.pend_usage, sessions=self.pend_sessions)

            ids = [c["id"] for c in bad if c.get("id")]
            self.validate()
            self.reproduce(only=ids)
            if len(self.defects()) >= len(bad) and len(self.violations()) >= len(viol):
                print("   줄지 않았다. 수선을 멈춘다.", flush=True)
                return

    def build(self):
        argv = ["pdf2anki.prequiz.build", str(self.out), "--deck", self.args.deck,
                "--id", self.args.id, "--jokbo-dir", self.args.jokbo_dir]
        if self.args.apkg_name:
            argv += ["--apkg-name", self.args.apkg_name]
        # 수선을 다 쓰고도 장수가 안 맞으면 **덱은 낸다.** 빈손으로 끝내는 것보다
        # 계약을 어긴 덱과 그 사실을 함께 주는 편이 낫다 — 판단은 사람이 한다.
        if self.args.allow_size or self.violations():
            if self.violations():
                print(f"⚠ 계약 위반이 남았다 — {' · '.join(self.violations())}", flush=True)
                print("   그래도 덱은 만든다. 위 위반을 보고 판단해라.", flush=True)
            argv += ["--allow-size"]
        self.sh(*argv)

    # ── 검수 자료와 장부 ───────────────────────────────────────
    def collect_check(self) -> Path | None:
        src = self.out / f"{self.args.id}_image_check.pdf"
        if not src.exists() or self.args.no_image_check:
            return None
        dst_dir = Path(self.args.check_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{Path(self.args.pdf_name).stem}_예습_image_check.pdf"
        shutil.copy2(src, dst)
        return dst

    def report(self, check: Path | None):
        rep = ledger.summarize(self.out, self.run)
        rep.update({"deck": self.args.deck, "id": self.args.id,
                    "pdf": self.args.pdf_name, "note": self.args.note or "",
                    "professor_stayed": self.stayed, "professors": self.prof,
                    "contract_violations": self.violations(),
                    "defects_left": len(self.defects()),
                    "wall_seconds": round(time.time() - self.t0, 1),
                    "image_check": str(check) if check else None})
        (self.out / "run.report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n" + ledger.table(rep["rows"], "── 이번 실행"))
        cum = rep["cumulative"]
        if abs(cum["cost_usd"] - rep["this_run"]["cost_usd"]) > 1e-6:
            print(f"\n이 강의 누적: {cum['seconds'] / 60:.0f}분 · ${cum['cost_usd']:.2f} "
                  f"· 토큰 {cum['tokens_total']:,} (앞선 실행 포함)")
        print(f"\n벽시계 {rep['wall_seconds'] / 60:.0f}분")

    def save_config(self):
        (self.out / CONFIG).write_text(json.dumps(
            {"deck": self.args.deck, "id": self.args.id, "pdf": str(self.args.pdf or ""),
             "pdf_name": self.args.pdf_name, "note": self.args.note or "",
             "subject": self.args.subject, "lecture": self.args.lecture,
             "professor_stayed": self.stayed, "professors": self.prof},
            ensure_ascii=False, indent=2), encoding="utf-8")

    def all(self):
        # **이름부터 적는다.** 뒤에 적으면 그 전에 끊긴 실행이 --resume 에서 이름을 잃는다
        # (덱이 `병리학::lecture::예습`, ID 가 `lecture` 로 떨어진다). 실제로 그렇게 됐다.
        self.save_config()
        self.step("자료 준비 (prep)", "prep.json", self.prep)
        self.step("예습 설명본", None, self.note)
        self.step("교수 확인", None, self.read_professor)
        self.step("출력 계약", None, self.schema)
        self.step("프롬프트 조립", "prompt.cards*.md", self.assemble)
        self.step("① 반드시 알아야 할 것", "must_know.json", self.must)
        self.step("검토·승인", "must_know.approved.json", self.approve)
        self.step("② 카드", "items.raw.json", self.cards)
        self.step("기계 검증", "items.checked.json", self.validate)
        # --skip-reproduce 면 산출물이 안 생긴다. 그걸 요구하면 실행이 죽는다.
        self.step("재현 검사",
                  None if self.args.skip_reproduce else "items.reproduced.json",
                  self.reproduce)
        self.repair()
        self.save_config()          # 교수 판정이 채워진 뒤 한 번 더
        self.step("덱 빌드", None, self.build)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="작년 자료로 예습 덱 하나를 굽는다")
    ap.add_argument("pdf", nargs="?", help="작년 필기 PDF")
    ap.add_argument("--note", help="예습 설명본. URL 이면 한 번 받아 note.md 로 굳힌다")
    ap.add_argument("--deck", help='덱 전체 이름. 주면 --subject·--lecture 를 덮는다')
    ap.add_argument("--lecture", "--deck-title",
                    help="덱의 가운데 마디로 쓸 **올해** 강의명. "
                         "기본은 작년 파일제목 원문 (복습 덱과 모으려면 양쪽에 같은 값)")
    ap.add_argument("--subject", default="과목",
                    help="덱의 첫 마디. 기본 '과목'. 빈 문자열이면 앞머리를 안 붙인다")
    ap.add_argument("--id", help="강의 ID (태그·파일명·guid 씨앗). 기본은 파일명의 [250825_01]")
    ap.add_argument("-o", "--out", help="작업 폴더. 기본 out/pre_<id>")
    ap.add_argument("--resume", help="이 폴더에서 이어서 돌린다")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 제목으로 자동 대조")
    ap.add_argument("--apkg-name", help="덱 파일 이름 (확장자 없이). 기본은 <강의 ID>_pre")
    ap.add_argument("--schema-dir", default="out/prequiz_schema")
    ap.add_argument("--model", help="빈 세션에 쓸 모델")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--hint", help="이 강의에만 거는 지시. ①② 프롬프트 끝에 붙는다")
    ap.add_argument("--stop-at-review", action="store_true",
                    help="반드시 알아야 할 것을 보여준 뒤 멈춘다")
    ap.add_argument("--skip-reproduce", action="store_true")
    ap.add_argument("--repair-rounds", type=int, default=2,
                    help="걸린 카드를 다시 쓰게 할 최대 횟수 (0이면 안 고친다)")
    ap.add_argument("--check-dir", default="out/_image_check",
                    help="이미지 카드 접촉 시트를 모아 둘 폴더")
    ap.add_argument("--no-image-check", action="store_true")
    ap.add_argument("--allow-size", action="store_true",
                    help=f"{MIN_CARDS}~{MAX_CARDS}장 계약을 어겨도 덱을 만든다")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    saved, given = {}, args.pdf
    if args.resume:
        cfg = Path(args.resume) / CONFIG
        if cfg.exists():
            saved = json.loads(cfg.read_text(encoding="utf-8"))
        args.pdf = args.pdf or saved.get("pdf") or None
        args.note = args.note or saved.get("note") or None

    if not args.resume and not args.pdf:
        print("작년 필기 PDF 경로가 필요하다 (또는 --resume <폴더>).")
        return 1
    pdf = Path(args.pdf) if args.pdf else None
    if pdf and not pdf.exists():
        print(f"PDF 를 찾지 못했다: {pdf}")
        return 1

    args.pdf_name = ((pdf.name if given and pdf else None)
                     or saved.get("pdf_name") or (pdf.name if pdf else "lecture.pdf"))
    named = bool(args.lecture)          # 올해 제목을 사람이 줬는가
    args.lecture = args.lecture or saved.get("lecture") or lecture_of(Path(args.pdf_name))
    args.deck = args.deck or saved.get("deck") or deck_of(args.lecture, args.subject)
    args.id = args.id or saved.get("id") or lecture_id_of(Path(args.pdf_name))

    out = Path(args.resume or args.out or f"out/pre_{args.id}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"덱   : {args.deck}")
    print(f"ID   : {args.id}   (guid 씨앗 {args.id}::pre — 복습 덱과 겹치지 않는다)")
    print(f"폴더 : {out.as_posix()}")
    if not named:
        print(f"\n작년 파일제목을 덱 노드로 썼다: 「{args.lecture}」")
        print("   복습 덱과 한 노드에 세우려면 양쪽에 --lecture 로 같은 값을 줘라")

    r = Runner(out, args)
    try:
        r.all()
    except (Failed, SessionError) as e:
        print(f"\n멈췄다 — {e}", flush=True)
        print(f"   고친 뒤 이 한 줄이면 이어서 간다: "
              f"python -m pdf2anki.prequiz.run --resume {out.as_posix()}")
        r.report(None)
        return 1

    chk = r.collect_check()
    print(f"\n끝났다.  덱: {out.as_posix()}/"
          f"{args.apkg_name or args.id + '_pre'}.apkg", flush=True)
    if chk:
        print(f"\n⚠ 눈으로 볼 것 — 이미지 카드 접촉 시트\n   {chk}", flush=True)
        print("   앞면 크롭 안에 정답이 인쇄돼 있는지만 본다.", flush=True)
    r.report(chk)
    return 0


if __name__ == "__main__":
    sys.exit(main())

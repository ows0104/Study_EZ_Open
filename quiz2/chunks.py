"""chunk마다 자기 구간만 담은 PDF를 만든다.

## 왜 자르나 — 토큰이 아니라 텍스트 레이어 때문이다

`Read`의 `pages` 인자로도 구간만 읽을 수 있으니 **토큰은 안 준다.** 어느 쪽이든
쪽 이미지 수는 같다. 자르는 값은 딴 데 있다.

    Read(원본, pages="7-11")   쪽 이미지만
    Read(조각.pdf)             쪽 이미지 + **텍스트 레이어**

`pages`를 생략해야 텍스트 레이어가 오는데, 원본은 60쪽이라 통째 읽기가 거부된다
(하네스 상한 20쪽). 조각은 5~9쪽이라 안 걸린다. **v1이 포기하고 있던 텍스트
레이어를 되찾는 것**이 이 모듈의 목적이다.

`260812_03` 실측:

    model_input.pdf 60쪽에 텍스트 11,703자 (평균 195자/쪽, 그림 위주 14쪽은 빈다)
    12쪽: "Results of mitochondrial damage / ATP depletion /
           Mitochondrial permeability transition pore / …"

원문 표기를 보존하라는 규칙(인터뷰 ⑯)이 픽셀 판독에 걸려 있었다 — `IL-13`인지
`IL-18`인지를 모델이 그림에서 읽어 옮겨 적고 있었다. 텍스트 레이어가 있으면
대조할 정본이 생긴다.

**아직 실측 안 한 것**: 이미지만 봤을 때 실제로 표기 오류가 얼마나 나는지 세어
본 적이 없다. 첫 편에서 확인할 항목이다.

## 값

    조각 7개 자르는 데 0.12초 (조각당 17ms)
    디스크 2.81MB → 3.34MB (1.19배. 조각마다 리소스 트리가 복제된다)
    텍스트 레이어 조각당 약 830토큰이 **늘어난다**

## 범위를 벗어나면 터뜨린다

`fitz.insert_pdf`는 범위를 넘기면 **말없이 잘라 준다.** 60쪽짜리에 50-66을
달라고 하면 11쪽을 주고 아무 말도 안 한다 — 족보 구간을 강의록 파일에 요청하면
정확히 그렇게 된다. 조용한 절반보다 시끄러운 실패가 낫다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class ChunkPdf:
    """한 조각이 받는 것. **두 채널과 필기 메모가 한 벌이다.**

    셋의 위계가 다르다는 것을 쓰는 쪽이 알아야 한다 (`HIERARCHY` 참조).
    """

    chunk_id: str
    slides: tuple[int, int]      # 각인 기준 슬라이드 번호 (1-based, 양끝 포함)
    path: Path                   # clean 채널. **사실 근거는 여기서만 나온다**
    pages: int
    text_chars: int              # 텍스트 레이어 분량
    blank_pages: int             # 텍스트가 거의 없는 쪽 (그림 위주)
    channel: str                 # 'lecture' | 'jokbo_tail' | 'jokbo_external'
    annot_path: Path | None = None   # 필기본. 같은 슬라이드에 필기가 얹힌 것
    notes_path: Path | None = None   # 이 구간의 annotations.json 조각
    note_count: int = 0              # 필기자가 적어 둔 말의 개수
    mark_count: int = 0              # 표시(상자·형광펜·밑줄)의 개수

    @property
    def has_text_layer(self) -> bool:
        """텍스트가 쓸 만큼 있는가. 없으면 조각이 그림만 보고 판단해야 한다.

        **총량이 아니라 쪽 비율로 잰다.** `260814_05`의 c1은 4쪽에 163자인데
        그 163자가 한 쪽에 몰려 있고 나머지 3쪽은 그림뿐이다. 총량으로 재면
        "텍스트 있음"이 나오지만 실제로는 대부분을 눈으로 봐야 한다.
        """
        return self.pages > 0 and self.blank_pages / self.pages < 0.5


# 텍스트가 이보다 적은 쪽은 그림 슬라이드로 본다. `260812_03`에서 60쪽 중 14쪽.
BLANK_TEXT_MAX = 40


# 조각에게 두 채널을 다 주기로 했으므로(관리자 결정), 무엇이 근거이고 무엇이
# 신호인지를 **프롬프트가 져야 한다.** v1은 이걸 구조로 지켰다 - 필기본을 아예
# 안 보여줬다. 그 방벽을 걷어내는 대신 말로 세운다.
#
# 프롬프트 조립하는 쪽이 이 문구를 그대로 싣는다.
HIERARCHY = """\
## 이 구간에 딸린 자료 셋 — 위계가 다르다

**같은 슬라이드가 두 번 온다. 슬라이드가 두 배로 있는 게 아니다.**
두 PDF는 같은 구간을 다른 채널로 렌더한 것이고, 각 쪽 좌상단의 노란 `Slide N`이
같으면 같은 슬라이드다.

1. **`<clean>` — 사실 근거.** 필기를 지운 강의록 본문이다.
   **q/a는 여기서 확인되는 것만 쓴다.**

2. **`<필기본>` — 중요도 신호.** 같은 슬라이드에 필기·형광펜·상자·도장이 얹혀
   있다. 어디를 강조했는지 보는 용도다. **여기에만 있고 clean에 없는 내용은
   근거가 아니다.** 색은 대개 빨강이 가장 강하고 파랑·초록 순으로 약해지는
   경향이 있으나 필기자마다 규약이 다를 수 있다.

3. **`<필기 메모>` — 필기자의 말과, 표시가 무엇을 덮었는지.** 위 필기본에서
   픽셀로 읽어야 할 것을 텍스트로 정리해 둔 것이다. `covers`는 그 상자가 덮은
   본문 낱말이다.

**예외는 하나뿐이다.** 필기에만 있고 clean 어디에도 없는 내용이라도, 족보가 그
지점을 실제로 물었다면 근거로 인정한다. 이때 `evidence_type`은 `annotation`이다.
족보와 이어지지 않는 순수 필기 사담은 `unsupported`다.
"""


def _segments_for(slides: tuple[int, int], prep: dict,
                  jokbo_tail: bool) -> list[tuple[str, Path, int, int]]:
    """슬라이드 구간을 파일별 조각으로 쪼갠다. `(채널, 파일, 첫쪽, 끝쪽)`.

    **구간 하나가 파일 둘에 걸칠 수 있다.** `260812_03`의 족보 구간은 50-66인데
    필기 꼬리 50-60은 `annotated.pdf`에, 외부 족보 61-66은 `jokbo_input.pdf`에
    있다. 한 채널로 잡으면 절반을 잃거나 범위를 벗어난다.

    슬라이드 번호는 각인 기준의 통짜 번호다. 강의록·필기 꼬리는 그대로 쪽
    번호이고, 외부 족보만 `jokbo_slide_offset`을 뺀다.
    """
    first, last = slides
    num_lecture = prep.get("num_lecture_pdf_pages") or prep.get("num_pages")
    external = prep.get("external_jokbo_range")
    ext_start = external[0] if external else None

    segments: list[tuple[str, Path, int, int]] = []

    # 필기 PDF 안쪽 (강의록 구간이거나 필기 꼬리 족보)
    inner_last = min(last, num_lecture)
    if first <= inner_last:
        if jokbo_tail:
            # 족보는 원본 그대로인 annotated 채널에서 읽는다 - 문항이 annotation
            # 이미지로만 있는 경우가 있어 clean 채널에서는 백지다.
            segments.append(("jokbo_tail", Path(prep["annotated_pdf"]),
                             first, inner_last))
        else:
            segments.append(("lecture", Path(prep["model_input_pdf"]),
                             first, inner_last))

    # 외부 족보 PDF 쪽
    if ext_start is not None and last >= ext_start:
        offset = prep.get("jokbo_slide_offset", 0)
        low = max(first, ext_start)
        segments.append(("jokbo_external", Path(prep["jokbo_input_pdf"]),
                         low - offset, last - offset))

    if not segments:
        raise ValueError(f"슬라이드 {first}-{last}이 어느 채널에도 안 걸린다.")
    return segments


def write_chunk_pdfs(run_dir: str | Path, *, out_name: str = "chunks",
                     jokbo_channel: str = "annotated") -> list[ChunkPdf]:
    """`structure.json`의 chunk마다 PDF를 하나씩 잘라 놓는다.

    `jokbo_channel`이 'annotated'면 필기 꼬리 구간을 원본 채널에서 읽는다.
    족보 구간은 chunk에 안 들어 있을 수 있으니 `jokbo_range`도 함께 낸다.
    """
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    notes_file = run_dir / "annotations.json"
    notes = json.loads(notes_file.read_text(encoding="utf-8")) if notes_file.exists() else []

    out_dir = run_dir / out_name
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted: list[tuple[str, tuple[int, int]]] = [
        (c["id"], (int(c["slides"][0]), int(c["slides"][1])))
        for c in structure.get("chunks", [])
    ]
    jokbo = structure.get("jokbo_range")
    if jokbo:
        wanted.append(("jokbo", (int(jokbo[0]), int(jokbo[1]))))

    made: list[ChunkPdf] = []
    for chunk_id, slides in wanted:
        is_jokbo = chunk_id == "jokbo"
        segments = _segments_for(slides, prep, jokbo_tail=is_jokbo)

        piece = fitz.open()
        for _, source, first, last in segments:
            with fitz.open(str(source)) as doc:
                # fitz는 범위를 넘기면 말없이 잘라 준다. 조용한 절반보다
                # 시끄러운 실패가 낫다.
                if first < 1 or last > doc.page_count:
                    raise ValueError(
                        f"{chunk_id}: 슬라이드 {slides[0]}-{slides[1]} 중 "
                        f"{source.name}의 {first}-{last}쪽을 달라고 했는데 "
                        f"그 파일은 {doc.page_count}쪽뿐이다. offset이 틀렸다."
                    )
                piece.insert_pdf(doc, from_page=first - 1, to_page=last - 1)

        target = out_dir / f"{chunk_id}.clean.pdf"
        piece.save(str(target), garbage=4, deflate=True, clean=True)

        text_chars = 0
        blank = 0
        for index in range(piece.page_count):
            length = len(piece.load_page(index).get_text().strip())
            text_chars += length
            if length < BLANK_TEXT_MAX:
                blank += 1
        pages = piece.page_count
        piece.close()

        # 필기본. 족보 조각은 이미 annotated에서 왔으므로 다시 만들지 않는다.
        annot_path = None
        if not is_jokbo:
            annot = fitz.open()
            with fitz.open(str(prep["annotated_pdf"])) as doc:
                annot.insert_pdf(doc, from_page=slides[0] - 1, to_page=slides[1] - 1)
            annot_path = out_dir / f"{chunk_id}.annot.pdf"
            annot.save(str(annot_path), garbage=4, deflate=True, clean=True)
            annot.close()

        # 이 구간의 필기 메모만 골라 낸다. 편 전체를 주면 조각이 남의 구간을
        # 읽고 근거로 쓴다.
        mine = [n for n in notes
                if slides[0] <= int(n.get("slide_no", 0)) <= slides[1]]
        notes_path = out_dir / f"{chunk_id}.notes.json"
        notes_path.write_text(json.dumps(mine, ensure_ascii=False, indent=1),
                              encoding="utf-8")

        made.append(ChunkPdf(
            chunk_id=chunk_id, slides=slides, path=target,
            pages=pages, text_chars=text_chars, blank_pages=blank,
            channel="+".join(s[0] for s in segments),
            annot_path=annot_path, notes_path=notes_path,
            note_count=sum(len(n.get("notes") or []) for n in mine),
            mark_count=sum(len(n.get("marks") or []) for n in mine),
        ))

    (out_dir / "index.json").write_text(json.dumps(
        [{"chunk_id": c.chunk_id, "slides": list(c.slides),
          "clean": str(c.path),
          "annot": str(c.annot_path) if c.annot_path else None,
          "notes": str(c.notes_path) if c.notes_path else None,
          "pages": c.pages, "text_chars": c.text_chars, "blank_pages": c.blank_pages,
          "channel": c.channel, "has_text_layer": c.has_text_layer,
          "note_count": c.note_count, "mark_count": c.mark_count} for c in made],
        ensure_ascii=False, indent=2), encoding="utf-8")
    return made


def report(made: list[ChunkPdf]) -> str:
    """사람이 보는 한 줄 요약. 텍스트 레이어가 없는 조각을 드러낸다."""
    lines = [f"{'조각':<8}{'슬라이드':>10}{'쪽':>4}{'텍스트':>9}{'빈쪽':>5}"
             f"{'말':>4}{'표시':>5}  채널"]
    for c in made:
        mark = "" if c.has_text_layer else "  ← 그림만"
        lines.append(f"{c.chunk_id:<8}{f'{c.slides[0]}-{c.slides[1]}':>10}"
                     f"{c.pages:>4}{c.text_chars:>9,}{c.blank_pages:>5}"
                     f"{c.note_count:>4}{c.mark_count:>5}  "
                     f"{c.channel}{mark}")
    thin = [c.chunk_id for c in made if not c.has_text_layer]
    if thin:
        lines.append(f"텍스트 레이어가 얇은 조각: {', '.join(thin)} — 그림을 봐야 한다")
    return "\n".join(lines)

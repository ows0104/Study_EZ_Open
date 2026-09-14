"""새 판이 왔다는 것을 시스템이 알아보는가.

2026-09-04 에 구멍 셋을 적어 두고 고쳤다. 여기서 지키는 것이 그 셋이다.

  ① 밤 쓸기가 갱신된 편에 아무 깃발도 안 실어 보냈다 — 그래서 아무것도 안 만들었다
  ② 문지기와 쓸기가 서로 다른 파일을 봐서, 「쓸기는 끝났다 / 문지기는 못 내보낸다」로
     편이 갇혔다
  ③ 판 번호가 같으면 내용이 갈려도 아무도 못 봤다 (`260903_03` 이 그랬다)
"""

import json

from runner import filenames, fingerprint, publish, watch

NAME_V1 = "[260902_02] 폐흡충증, 장흡충증(신은희)_박준원v1.pdf"
NAME_V2 = "[260902_02] 폐흡충증, 장흡충증(신은희)_박준원v2.pdf"


def _pdf(root, name, body=b"%PDF-1.4 v1"):
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_bytes(body)
    return path


def _run_dir(runs, run_id, source_name, sha):
    d = runs / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "prep.json").write_text(json.dumps(
        {"source": source_name, "source_sha256": sha, "slides": 3, "pages": []}),
        encoding="utf-8")
    return d


# ── ③ 이름이 같은데 내용이 갈렸다 ────────────────────────────────

def test_같은_판_번호라도_내용이_갈리면_잡는다(tmp_path):
    pdf = _pdf(tmp_path / "필기", NAME_V1, b"%PDF old")
    item = filenames.parse(pdf)
    _run_dir(tmp_path / "runs", "260902_02", NAME_V1, fingerprint.sha256_of(pdf))

    same = fingerprint.compare(tmp_path / "runs" / "260902_02", pdf, item.version)
    assert same.state == fingerprint.SAME
    assert same.by_hash

    pdf.write_bytes(b"%PDF old and a little more")     # 이름은 그대로다
    now = fingerprint.compare(tmp_path / "runs" / "260902_02", pdf, item.version)
    assert now.state == fingerprint.CONTENT_CHANGED
    assert now.stale


def test_지문이_없는_옛_편은_판_번호로만_본다(tmp_path):
    pdf = _pdf(tmp_path / "필기", NAME_V1)
    item = filenames.parse(pdf)
    run = tmp_path / "runs" / "260902_02"
    run.mkdir(parents=True)
    (run / "run.config.json").write_text(json.dumps({"pdf_name": NAME_V1}), encoding="utf-8")

    got = fingerprint.compare(run, pdf, item.version)
    assert got.state == fingerprint.SAME
    assert not got.by_hash            # 잰 것이 아니라 못 잰 것이다. 구별해서 들고 있는다


# ── ② 기록이 산출물보다 앞서도 갇히지 않는다 ─────────────────────

def test_source_json만_새_판이면_다시_만들_대상이다(tmp_path):
    """쓸기가 아무것도 안 만들고 표시만 찍은 자리. 예전에는 여기서 영원히 갇혔다."""
    pdf = _pdf(tmp_path / "필기", NAME_V2)
    item = filenames.parse(pdf)
    run = _run_dir(tmp_path / "runs", "260902_02", NAME_V1, "옛지문")
    (run / "source.json").write_text(json.dumps(
        {"stem": NAME_V2[:-4], "version": 2, "size": 1, "mtime": 1}), encoding="utf-8")

    got = fingerprint.compare(run, pdf, item.version)
    assert got.state == fingerprint.NEWER_VERSION      # 산출물(prep.json)은 아직 v1 이다
    assert watch._already_built(tmp_path / "runs", "260902_02", item) is None


def test_문지기와_쓸기가_같은_값을_본다(tmp_path):
    pdf = _pdf(tmp_path / "필기", NAME_V1, b"%PDF old")
    item = filenames.parse(pdf)
    run = _run_dir(tmp_path / "runs", "260902_02", NAME_V1, fingerprint.sha256_of(pdf))
    (run / "run.config.json").write_text(
        json.dumps({"pdf": str(pdf), "pdf_name": NAME_V1}), encoding="utf-8")

    owned, note = publish._owns(run, item)
    assert owned and not note

    pdf.write_bytes(b"%PDF new content, same name")
    owned, note = publish._owns(run, item)
    assert owned and "다르다" in note                  # 문지기가 붙잡는다
    assert watch._already_built(tmp_path / "runs", "260902_02", item) is None   # 쓸기도 집는다


# ── ① 갱신된 편에는 깃발이 실린다 ────────────────────────────────

def _item(reason):
    return watch.WorkItem(subject="기생충학", run_id="260902_02", key="260902_02",
                          date="2026-09-02", title="폐흡충증", this_pdf="x.pdf",
                          this_version=2, reason=reason)


def test_갱신된_편에는_revise_가_실린다():
    assert watch.build_extra(_item("new")) == []
    assert watch.build_extra(_item("newer_version")) == ["--revise"]
    assert watch.build_extra(_item("content_changed")) == ["--revise"]


def test_사람이_force_를_줬으면_revise_를_덧붙이지_않는다():
    assert watch.build_extra(_item("newer_version"), ["--force"]) == ["--force"]


def test_큐가_갱신_사유를_적는다(tmp_path):
    _pdf(tmp_path / "기생충학" / "필기" / "2026", NAME_V2)
    _run_dir(tmp_path / "runs", "260902_02", NAME_V1, "옛지문")

    queue = watch.build_queue(root=tmp_path, subjects=["기생충학"], this_year="2026",
                              runs_dir=tmp_path / "runs", min_age_seconds=0)
    assert [i.reason for i in queue.items] == ["newer_version"]
    assert any("v1" in n and "v2" in n for n in queue.items[0].notes)

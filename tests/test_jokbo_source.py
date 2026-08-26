"""기출 원본을 못 찾은 채로 굽지 않는다.

`--jokbo-dir` 의 기본값(`out/jokbo`)은 이 저장소의 배치(`runs/_jokbo/<과목>`)와
다르다. 자동 흐름(`studyez`)은 항상 옳은 값을 넘기지만 손으로 부르면 기본값이
먹는다. 2026-08-26에 그걸로 26편을 다시 구우면서 **기출 카드 뒷면의 지면 이미지가
통째로 빠졌다** — `260819_01` 은 미디어가 66 → 57 이 됐다.

빠진 것이 미디어뿐이라 노트 수도 카드 수도 그대로였고, 그래서 `verify` 도
`studyez/gate.py` 도 못 잡았다. 막을 자리는 굽기 전이다.
"""

import json

from pdf2anki.build import jokbo_dir_candidates, main


def _card(source_type: str, n: int) -> dict:
    return {
        "id": f"c{n}", "q": f"질문 {n}", "a": f"답 {n}", "explanation": None,
        "slide_no": None if source_type == "jokbo" else 1,
        "card_format": "basic", "card_type": "fact", "importance": "core",
        "source_type": source_type,
        "evidence_type": "jokbo_question" if source_type == "jokbo" else "lecture_text",
        "exam_hit": False, "media": None,
        "reproduce": {"verdict": "same", "reason": None},
    }


def _prep_dir(tmp_path, jokbo_cards: int):
    d = tmp_path / "run"
    d.mkdir()
    cards = [_card("lecture", 1)] + [_card("jokbo", 10 + i) for i in range(jokbo_cards)]
    (d / "items.reproduced.json").write_text(
        json.dumps({"cards": cards}, ensure_ascii=False), encoding="utf-8")
    (d / "prep.json").write_text(
        json.dumps({"slides": 1, "pages": []}, ensure_ascii=False), encoding="utf-8")
    return d


def _argv(d, tmp_path, *extra):
    return [str(d), "--deck", "과목::강의", "--id", "ptest",
            "--jokbo-dir", str(tmp_path / "없는곳"), *extra]


def test_기출_카드가_있는데_원본을_못_찾으면_굽지_않는다(tmp_path, capsys):
    d = _prep_dir(tmp_path, jokbo_cards=3)
    assert main(_argv(d, tmp_path)) == 1
    out = capsys.readouterr().out
    assert "기출 카드가 3장인데" in out
    assert not list(d.glob("*.apkg"))


def _run_past_guard(argv, capsys) -> str:
    """문지기를 지나면 그 뒤 굽는 단계에서 어떻게든 터진다(빈 prep 이라 미디어가 없다).

    여기서 재는 것은 **문지기가 무엇을 했는가**뿐이므로, 뒤에서 난 예외는 삼키고
    그때까지 찍힌 글만 돌려준다. `pytest.raises` 로 두면 아무거나 터져도 통과한다.
    """
    try:
        main(argv)
    except BaseException:
        pass
    return capsys.readouterr().out


def test_기출_카드가_없으면_원본이_없어도_막지_않는다(tmp_path, capsys):
    """강의록만으로 된 편은 족보가 아예 필요 없다. 여기서 막으면 멀쩡한 편이 선다."""
    out = _run_past_guard(_argv(_prep_dir(tmp_path, jokbo_cards=0), tmp_path), capsys)
    assert "기출 카드가" not in out
    assert "--no-jokbo-images" not in out


def test_일부러_뺄_때는_강행할_수_있다(tmp_path, capsys):
    d = _prep_dir(tmp_path, jokbo_cards=2)
    out = _run_past_guard(_argv(d, tmp_path, "--no-jokbo-images"), capsys)
    assert "기출 카드가 2장인데" in out          # 경고는 그대로 나온다
    assert "--no-jokbo-images 로 강행한다" in out


def test_어디를_봐야_하는지_알려_준다(tmp_path):
    (tmp_path / "runs" / "_jokbo" / "병리학").mkdir(parents=True)
    (tmp_path / "runs" / "_jokbo" / "병리학" / "index.json").write_text("{}", encoding="utf-8")
    (tmp_path / "out" / "jokbo").mkdir(parents=True)
    (tmp_path / "out" / "jokbo" / "index.json").write_text("{}", encoding="utf-8")

    found = [p.as_posix() for p in jokbo_dir_candidates(tmp_path)]
    assert any(p.endswith("out/jokbo") for p in found)
    assert any(p.endswith("runs/_jokbo/병리학") for p in found)


def test_index가_없으면_후보도_없다(tmp_path):
    (tmp_path / "runs" / "_jokbo" / "병리학").mkdir(parents=True)
    assert jokbo_dir_candidates(tmp_path) == []

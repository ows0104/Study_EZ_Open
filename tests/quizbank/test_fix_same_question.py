"""A fix asks what the question asked (docs/changes/2026-11-23-fix-same-question/spec.md).

R1 (fix.md) and R2 (item-review.md) are prompt rules; the tests pin their sentences. Cases: 레오 Q038 (「보호효과가
없다는 뜻인가」 → 「지속기간은?」), 신종 Q075 (judgment → distribution), 진균 Q087 (reason → diagnostic test list)."""
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[2] / 'content' / 'prompts' / 'learning-links' / 'v4'


def prompt(name):
    return (PROMPTS / name).read_text(encoding='utf-8')


def test_a_fix_keeps_the_question_it_was_given():
    text = prompt('fix.md')
    assert '**고친 문항은 원래 문항이 묻던 것을 묻는다.**' in text
    assert '같은 ID로 다른 것을 물으면 원래 물음은 은행에서 사라지고 기록은 다른 물음에 이어진다' in text
    assert '판단·이유·기전을 묻던 문항을 목록·수치·분포 같은 다른 사실을 묻는 문항으로 바꾸지 않는다' in text
    assert '같은 물음 안에서 형식(basic·ox·cloze·객관식)·발문·정답·채점 단위를 고친다' in text


def test_three_changes_stay_inside_the_same_question():
    """User 2026-11-23 liked Q006 (one answer → the three candidates the source lists), Q156 and Q011 (the same list
    completed) and Q081 (one layer kept): a fix still does these."""
    text = prompt('fix.md')
    assert '틀리거나 원본이 정하지 않은 정답을 원본에 맞는 정답으로 바꾸는 것(원본이 후보를 함께 들면 그 후보 모두)' in text
    assert '같은 범주 목록의 빠진 원소를 채우는 것(발문에 주던 같은 목록의 원소를 답으로 옮기는 것, input.existence의 components를 채우는 것 포함)' in text
    assert '답을 줄이거나 나누어 원본이 쓰는 한 층으로 맞추는 것' in text


def test_a_finding_that_asks_another_question_is_not_applied_to_the_id():
    text = prompt('fix.md')
    assert '지적이 다른 물음을 요구하면' in text
    assert '그 부분은 이 ID에 적용하지 않는다. 이 문항은 원래 물음 안에서 고치고, 적용하지 않은 이유를 exam_rationale에 한 줄 남긴다' in text
    assert '따로 물을 내용은 이 문항에 싣지 않는다' in text


def test_a_review_fix_stays_inside_what_the_question_asks():
    text = prompt('item-review.md')
    assert '**fix는 그 문항이 묻는 것 안에서 고칠 방향이다.**' in text
    assert '묻는 대상·범주를 바꾸라고(다른 대상을 묻게, 판단·이유·기전 문항을 목록·수치 문항으로, 「존재 문항으로」) 쓰지 않는다' in text
    assert '같은 범주 목록의 빠진 원소를 채우라, 틀린 정답을 원본 정답으로 바꾸라, input.existence의 존재 문항에 빠진 components를 채우라는 것은 같은 물음 안이다' in text
    assert '「지식 없이 문구로 풀린다」는 지적도 같은 물음을 지식이 있어야 풀리는 형식·발문으로 바꾸는 방향으로 쓴다' in text
    assert '따로 물을 것이 있으면 note에 「별도 문항: …」으로 적는다' in text
    assert '그 이유만으로 design을 doubt·wrong으로 하지 않는다' in text


def test_the_rules_sit_where_the_stages_read_them():
    """fix.md's rule is in the opening list the fix follows for every question; item-review's is under the fix field."""
    fix = prompt('fix.md')
    assert fix.index('**고친 문항은 원래 문항이 묻던 것을 묻는다.**') < fix.index('## 충돌')
    review = prompt('item-review.md')
    assert review.index('- note: 지적의 근거. fix: 고칠 방향.') < review.index('**fix는 그 문항이 묻는 것 안에서 고칠 방향이다.**') \
        < review.index('- prerequisite_checks:')

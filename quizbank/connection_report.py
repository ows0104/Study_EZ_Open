"""Human-readable, non-executable Markdown from a validated review package."""
from __future__ import annotations

import html
import json
from collections import Counter

from studyez_contracts.learning_links.validate import bank_questions


def escape(value):
    # Authored strings are data, including Markdown links, HTML, and table delimiters.
    text = html.escape(str(value), quote=True).replace("\r\n", "\n").replace("\r", "\n")
    for token in ("\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "!", "|", "~"):
        text = text.replace(token, "\\" + token)
    return text.replace("\n", "<br>")


def references(refs):
    return "; ".join(f"{r['source_id']} · {r['locator']} · 물리쪽 {','.join(map(str, r['pages'])) or '미지정'}" for r in refs) or "근거 미기재"


def render_report(review, bank):
    """Render only supplied facts/claims; do not create a priority or learning score."""
    lines = ["# 연결 검토 묶음", "",
             f"강의: {escape(review['lecture_id'])} · 범위: {escape(review['scope']['label'])}", "",
             "**구조 검사 결과입니다. 의학적 정답·콘텐츠 공개·학습 완료를 인증하지 않습니다.**", "",
             f"입력의 검토 주장: {escape(review['provenance']['status'])} · "
             f"독립 포인트 근거: {escape(review['provenance']['independent_points'])}",
             f"작성/검토 경로: {escape(review['provenance']['method'])} · "
             f"검토자: {escape(review['provenance']['reviewer'])}",
             f"이력 메모: {escape(review['provenance']['notes'])}", "", "## 범위와 한계", ""]
    for field, label in (("included", "포함"), ("excluded", "제외"), ("reviewed", "실제 검토"), ("limitations", "한계")):
        lines.append(f"- {label}: {escape('; '.join(review['scope'][field]) or '기재 없음')}")
    lines += [f"- 목록 밖 누락 검토: {escape(review['scope']['outside_list_review'])}", ""]
    lines += ["## 기존 은행의 검수·충돌 기록", "",
              "아래는 입력 은행의 기존 기록이며 이 도구가 새로 판정하거나 통과시킨 결과가 아닙니다.", "",
              f"검수: {escape(json.dumps(bank.get('validation', '기재 없음'), ensure_ascii=False, sort_keys=True))}", "",
              f"출처 충돌: {escape(json.dumps(bank.get('source_conflicts', '기재 없음'), ensure_ascii=False, sort_keys=True))}", ""]
    counts = Counter(c["status"] for c in review["coverage"])
    lines += ["## 포인트 대조 현황", "",
              " · ".join(f"{key}: {counts[key]}" for key in ("covered", "partial", "gap", "unknown", "excluded")),
              "", "이 수치는 콘텐츠 대조 결과이며 사용자 학습률이 아닙니다.", ""]
    concepts = {c["concept_id"]: c for c in review["concepts"]}
    targets = {t["target_id"]: t for t in review["targets"]}
    questions = bank_questions(bank)
    roles = {"root": "뼈대", "branch": "가지", "leaf": "세부"}
    for concept in review["concepts"]:
        lines += [f"## {escape(concept['label'])} ({escape(concept['concept_id'])})", "",
                  f"상위 위치: {escape('; '.join(concepts[p]['label'] for p in concept['parent_ids']) or '최상위')}", ""]
        for target in review["targets"]:
            if concept["concept_id"] in target["concept_ids"]:
                lines += [f"- {escape(target['target_id'])}: {escape(target['title'])} ({roles[target['role']]})"]
        lines.append("")
    lines += ["## 관계 전체 대조", "", "| 관계 | 연결·유형·조건 | 검토 상태·근거 | 목표 |", "|---|---|---|---|"]
    for relation in review["relations"]:
        rid = relation["relation_id"]
        linked = [t["target_id"] for t in targets.values() if rid in t["relation_ids"]]
        label = f"{relation['from_id']} → {relation['to_id']} / {relation['kind']} / {relation['condition']}"
        basis = f"{relation['review_status']}: {relation['reason']} / {references(relation['evidence'])}"
        lines.append(f"| {escape(rid)} | {escape(label)} | {escape(basis)} | {escape(', '.join(linked) or '목표 연결 없음 — 검토 필요')} |")
    for target in targets.values():
        tid = target["target_id"]
        lines += ["", f"## 목표 {escape(tid)}: {escape(target['title'])}", "",
                  f"역할: {roles[target['role']]} · 선정 이유: {escape(target['reason'])}",
                  f"근거: {escape(references(target['evidence']))}", ""]
        for axis, label in (("structural", "강의 이해"), ("exam", "시험"), ("clinical", "임상")):
            item = target["importance"][axis]
            lines += [f"- {label}: {escape(item['status'])} — {escape(item['reason'])}"]
            for basis in item["evidence"]:
                lines += [f"  - {escape(basis['kind'])}: {escape(basis['reason'])} / {escape(references(basis['refs']))}"]
        for direction in target["directions"]:
            did = direction["direction_id"]
            lines += ["", f"### 방향 {escape(did)} ({escape(direction['requirement'])})", "",
                      f"단서: {escape(direction['cue'])}", f"회상할 답 범위: {escape(direction['answer_scope'])}",
                      f"확인할 관계: {escape(', '.join(direction['relation_ids']))}", ""]
            mappings = [m for m in review["mappings"] if m["direction_id"] == did]
            if not mappings:
                lines += ["연결 문항 없음. 필요한 질문/검토를 준비해야 합니다.", ""]
            for mapping in mappings:
                question = questions[mapping["question_id"]]
                lines += [f"- 문항 {escape(mapping['question_id'])}: {escape(question['question'])}",
                          f"  - 정답: {escape(question['answer'])}",
                          f"  - 실제 시험: {escape(', '.join(mapping['tested_relation_ids']) or '없음')}",
                          f"  - 발문 제공: {escape(', '.join(mapping['provided_relation_ids']) or '없음')}",
                          f"  - 해설에만 등장: {escape(', '.join(mapping['explanation_relation_ids']) or '없음')}",
                          f"  - 판정 이유: {escape(mapping['reason'])}"]
                # Preserve complex choices/pairs and existing caveats in the reviewer view.
                detail = {k: v for k, v in question.items() if k not in ("question_id", "question", "answer")}
                lines += [f"  - 원문 부가 필드: {escape(json.dumps(detail, ensure_ascii=False, sort_keys=True))}"]
    lines += ["", "## 포인트별 충족·부족한 질문·미확인", ""]
    points = {p["point_id"]: p for p in review["points"]}
    for check in review["coverage"]:
        point = points[check["point_id"]]
        lines += [f"### {escape(check['point_id'])}: {escape(point['text'])}", "",
                  f"판정: {escape(check['status'])} — {escape(check['reason'])}",
                  f"근거: {escape(references(point['evidence']))}",
                  f"범위 판단: {escape(point['scope_status'])} — {escape(point['reason'])}", ""]
        for key, label in (("confirmed_direction_ids", "확인"), ("partial_direction_ids", "일부만 시험"),
                           ("missing_direction_ids", "부족한 질문"), ("unknown_direction_ids", "미확인")):
            lines.append(f"- {label}: {escape(', '.join(check[key]) or '없음')}")
        if check["exclusion_basis"]:
            lines.append(f"- 제외 근거 종류: {escape(check['exclusion_basis'])}")
        lines.append("")
    leaves = [t["target_id"] for t in targets.values() if t["role"] == "leaf"]
    lines += ["## 세부와 출처", "", f"세부 목표: {escape(', '.join(leaves) or '이 묶음에 기재 없음')}",
              "세부 목표가 없거나 뼈대가 covered여도 강의 전체 학습 완료를 뜻하지 않습니다.", ""]
    for source in review["sources"]:
        lines.append(f"- {escape(source['source_id'])}: {escape(source['label'])} / {escape(source['kind'])} / "
                     f"교수 {escape(source['professor'] or '미상')} / 연도 {escape(source['year'] or '미상')} / "
                     f"쪽수(입력 선언) {escape(source['page_count'] or '미상')} / SHA256 {source['sha256']}")
    return "\n".join(lines) + "\n"

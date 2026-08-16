"""빌드된 .apkg를 열어 실제 내용물을 확인한다.

genanki가 예외 없이 반환했다는 사실은 "덱이 제대로 만들어졌다"와 다르다.
미디어 파일이 하나 빠지거나 노트가 조용히 덜 들어가도 write_to_file은 성공한다.
그 덱은 Anki에서 import될 때까지, 최악의 경우 시험 전날 복습하다가 그림이
안 뜰 때까지 아무도 모른다.

그래서 쓴 파일을 도로 열어본다. zip 안의 sqlite에서 노트/카드 수를 직접 세고,
미디어 매핑에 이름이 다 있는지 대조한다. 몇 초면 끝나고 실패는 확정적이다.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

# genanki 버전에 따라 컬렉션 파일 이름이 다르다. 새 스키마부터 본다.
_COLLECTION_NAMES = ("collection.anki21b", "collection.anki21", "collection.anki2")


class ApkgVerificationError(RuntimeError):
    pass


def _find_collection(names: list[str]) -> str | None:
    for name in _COLLECTION_NAMES:
        if name in names:
            return name
    return None


def verify_apkg(apkg_path, expected_notes: int, expected_media: list[str]) -> dict:
    """(노트 수, 카드 수, 미디어 수)를 실제로 세어 기대값과 대조한다.

    expected_media는 collection.media에 들어가야 할 파일명 목록이다.
    문제가 있으면 ApkgVerificationError를 던진다.
    """
    apkg_path = Path(apkg_path)
    problems: list[str] = []

    if not apkg_path.exists():
        raise ApkgVerificationError(f"apkg가 없습니다: {apkg_path}")
    if apkg_path.stat().st_size < 1024:
        problems.append(f"파일이 비정상적으로 작습니다 ({apkg_path.stat().st_size} bytes)")

    note_count = card_count = 0
    media_names: set[str] = set()

    with zipfile.ZipFile(apkg_path) as zf:
        names = zf.namelist()
        collection = _find_collection(names)
        if not collection:
            raise ApkgVerificationError(
                f"apkg 안에 컬렉션 파일이 없습니다. 들어 있는 것: {names[:10]}")

        if expected_media:
            if "media" not in names:
                problems.append("미디어를 넣었는데 media 매핑 파일이 없습니다")
            else:
                media_map = json.loads(zf.read("media").decode("utf-8"))
                media_names = set(media_map.values())
                missing = sorted(set(expected_media) - media_names)
                if missing:
                    problems.append(
                        f"패키지에 빠진 미디어 {len(missing)}개: {missing[:5]}")
                # 매핑에만 있는 이름 = 실제 zip 엔트리가 없을 수 있다.
                for key in media_map:
                    if key not in names:
                        problems.append(f"media 매핑에 있으나 zip에 없는 항목: {key}")
                        break

        # anki21b는 zstd 압축이라 sqlite로 못 연다. 그때는 노트 수 검증을 건너뛰되
        # 조용히 넘기지 않고 결과에 남긴다.
        if collection == "collection.anki21b":
            problems.append("collection.anki21b(압축 스키마)라 노트 수를 세지 못했습니다")
        else:
            with tempfile.TemporaryDirectory() as td:
                zf.extract(collection, td)
                conn = sqlite3.connect(str(Path(td) / collection))
                try:
                    note_count = conn.execute("select count(*) from notes").fetchone()[0]
                    card_count = conn.execute("select count(*) from cards").fetchone()[0]
                finally:
                    conn.close()
            if note_count != expected_notes:
                problems.append(f"노트 수 불일치: 기대 {expected_notes}, 실제 {note_count}")
            if card_count != expected_notes:
                problems.append(f"카드 수 불일치: 기대 {expected_notes}, 실제 {card_count}")

    if problems:
        raise ApkgVerificationError(
            "apkg 검증 실패:\n" + "\n".join(f"  - {p}" for p in problems))

    return {
        "collection": collection,
        "notes": note_count,
        "cards": card_count,
        "media": len(media_names),
    }

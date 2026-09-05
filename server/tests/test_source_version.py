"""덱을 무슨 판으로 구웠나 — 파일명에서 읽는다.

파이프라인은 `run.meta.json`에 원본 PDF 이름을 적어 두고, 그 이름 꼬리에 필기자와
판 번호가 붙어 있다(`[260811_01] 세포 손상_최나예v2.pdf`). 관리 화면의 「퀴즈」 탭이
그 값을 지금 필기의 판과 견줘 **옛 자료로 구운 덱**을 표시한다.

규칙은 `studyez/filenames.py`의 `_AUTHOR_RE`와 같다. 서버는 따로 배포되어 그쪽을
import 할 수 없어 복제해 두었고, 한쪽을 고치면 다른 쪽도 고쳐야 한다.

    server/.venv/Scripts/python.exe -m tests.test_source_version
"""

from __future__ import annotations

from app.naming import version_from_filename

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def main() -> None:
    print("판 번호를 읽는다")
    for name, want in [
        ("[260811_01] 세포 손상_최나예v2.pdf", 2),
        ("[260811_01] 세포 손상_고명재 v3.pdf", 3),
        ("[260811_01] 세포 손상_오서연_v4.pdf", 4),
        ("[260811_01] 세포 손상_이채현v.1.pdf", 1),
    ]:
        got = version_from_filename(name)
        check(f"{name[-18:]} → v{want}", got == want, got)

    print()
    print("판 번호가 없으면 첫 판이다")
    # `_박지민`처럼 이름만 붙은 것. `filenames.py`가 v1으로 읽는 것과 같은 판단이다.
    got = version_from_filename("[260811_01] 세포 손상_박지민.pdf")
    check("이름만 붙은 것은 v1", got == 1, got)

    print()
    print("경로가 붙어 있어도 읽는다")
    for name in ["/volume1/필기/2026/[260811_01] 세포_최나예v2.pdf",
                 r"D:\필기\2026\[260811_01] 세포_최나예v2.pdf"]:
        got = version_from_filename(name)
        check(f"{name[:12]}… → v2", got == 2, got)

    print()
    print("모르면 모른다고 한다")
    # **1로 메우지 않는다.** 메우면 「지금 판과 같다」로 읽혀 다시 구울 이유가 사라진다.
    for name in ["아무렇게나 지은 이름.pdf", ""]:
        got = version_from_filename(name)
        check(f"{name or '빈 문자열'!r} → None", got is None, got)

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()

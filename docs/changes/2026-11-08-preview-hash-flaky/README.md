# 미리보기 원본 해시 검사의 간헐 실패 수정

## 의도

사용자 2026-11-08 요청: GitHub Actions 실패 점검 뒤 「Fix it」.
PR #23의 PR 실행(42392133878, Windows 러너)에서
`tests/runner/test_preview_sources.py::test_selection_hash_changes_when_source_bytes_change`가 실패했고,
같은 코드의 master 병합 실행에서는 통과했다. #14 완료 기록의 「기존 mtime 간헐 실패」와 같은 종류다.

## 원인

`runner/preview_sources.py`의 `_digest`는 `lru_cache`로 (경로, 크기, mtime_ns)를 키로 쓴다.
검사는 원본 `"2025 포도알균 김범준 1"`(29바이트)을 `b'new revision with new content'`(29바이트)로 다시 쓴다.
크기가 같고, 빠른 두 번 쓰기가 Windows에서 같은 mtime을 받으면 캐시가 옛 해시를 돌려준다.

재현: 같은 검사 본문에서 다시 쓴 뒤 `os.utime`으로 원래 mtime을 되돌리면 두 해시가 같아진다(확인함).

## 수정

검사만 고쳤다. 같은 크기 다시 쓰기는 유지하고(캐시 키를 mtime만 가르는 상황을 그대로 검사),
다시 쓴 뒤 mtime을 원래보다 1초 뒤로 명시해 파일시스템 시계와 경주하지 않게 했다.
같은 크기라는 전제도 assert로 고정했다.

런타임 코드·DB·출제·운영은 바꾸지 않았다.

## 남는 한계

실제 운영에서 같은 경로의 파일이 같은 크기로, 같은 mtime 틱 안에 다시 쓰이면 캐시가 옛 해시를 낼 수 있다.
필기 PDF가 그렇게 바뀌는 일은 사실상 없어 이번 범위에서는 고치지 않았다.

## 검사

- 수정한 검사 30회 연속 통과
- `tests/runner/test_preview_sources.py` 18개 통과
- PR CI(Tests and build)

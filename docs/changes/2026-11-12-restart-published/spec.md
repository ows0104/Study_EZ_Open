# Main-Quiz 공개된 판 새로 출제(관리자 명시) — 설계

## 요구사항과 수용 기준
- `RequestIn.replacePublished`(기본 False). `restart` 없이 보내면 422.
- `restart_target`: 플래그가 있으면 게시된(job done) 최근 요청도 대상이 된다. 진행·대기 중, 다른 관리자 소유는 그대로 409.
- 공개된 판(control.revision) 거절은 `restart` + `replacePublished`일 때만 건너뛴다.
- packet에 `replacePublished: true`를 남긴다(입력 지문에 포함).

## 책임·입출력 계약·오류 상태
- `server/app/routes/root_generation.py`만. 러너·생성기·DB 스키마 불변.

## 호환성과 데이터 보존
- 옛 요청·옛 판·RootEvent는 바뀌지 않는다. `put_result`의 baseline 대조는 그대로라 그 사이 공개 설정이 바뀌면 게시가 거절된다.

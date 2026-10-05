# 로컬 실행 데이터

폴더 판정의 정본은 [runner/runlayout.py](../runner/runlayout.py)다.
현재 러너는 시도마다 폴더를 만들고, 선택한 결과를 강의 폴더의 배포 위치에 둔다.
과거처럼 파일이 강의 폴더에 바로 있는 구조도 읽을 수 있다.

## 구조

```text
runs/
  <run_id>/
    main/<판>/             복습 생성 시도
    prequiz/<판>/          예습 생성 시도
    *.apkg                 현재 배포할 덱
    run.meta.json          복습 계약
    pre_run.meta.json      예습 계약
    main_items.final.json  복습 웹 문항
    pre_items.final.json   예습 웹 문항
    slides/                웹 근거 슬라이드
    CHOSEN.json            선택한 시도와 사람이 적은 이유
    HOLD                   배포 보류 사유
    preview.md             예습 대화
    pre_target.json        예습 대상인 올해 강의
    note.md                사용자 메모
    source.json            원본 지문
    BUILDING               생성 중 표시
  _materials/<과목>/<판>/   판별 족보 컷
  _pairs/<과목>.json        사람이 확인한 연도별 강의 매칭
```

`<판>`은 `YYMMDD-HHMM` 형식이다. 같은 분의 충돌을 구별하는 접미사가 붙을 수 있다.
일부 도구는 `out/`를 독립 실험 출력으로 사용한다. 모든 결과가 `runs/`에 있다고
가정하지 말고 실제 명령의 `--out`·`--resume`을 확인한다.

## 어떤 시도를 읽나?

`runlayout.work_dir`는 명시한 판이 있으면 그 판을, 없으면 다음 순서로 찾는다.

1. `CHOSEN.json`이 선택한 시도
2. 배포 메타데이터의 `attempt`
3. 가장 새 판 폴더
4. 강의 폴더 자체(옛 구조)

최신 폴더가 미완성 실험일 수 있으므로 단순 mtime 정렬로 이 결정을 대신하지 않는다.
시도 식별은 카드 내용 해시를 사용한다. 경로는 사람이 찾는 용도이며,
선택 기록과 실제 배포 카드가 다르면 `gate`가 덱 업로드를 보류한다.

`runner chosen`은 이유를 기록하고, `runner promote`는 해당 시도를 배포 위치로 옮긴다.
명령 예시는 [명령 안내](commands.md#선택재빌드업로드)에 있다.

## 보존·정리

`runlayout.HUMAN_FILES`·`PUBLISHED_FILES`·`RUNTIME_FILES`와
`is_lecture_own`이 보존 대상을 정의한다. 폴더 정리 코드에 목록을 다시 복제하지 않는다.
특히 사용자 메모·매칭·대화·선택 이유는 PDF에서 재생성할 수 없다.

족보를 다시 자를 때는 새 판을 만든다. 이미 만든 카드의 `jokbo.used.json`이 과거 컷을
가리킬 수 있으므로 참조 여부를 확인한 뒤 정리한다.
자르는 명령에는 과목 폴더를, 카드를 만드는 명령에는 실제 컷 판 폴더를 전달한다.

과거 폴더 이행·실측 기록은 [변경 전 문서](archive/2026-10-06-originals/docs/runs-layout.md)에 보관했다.

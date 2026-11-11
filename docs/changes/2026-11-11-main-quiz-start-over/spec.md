# Main-Quiz 새로 출제 — 설계

## 요구사항과 수용 기준
- R1 화면: 최근 판이 공개 전이고 끝났다(실패·중지; 대기·진행·웹 응답 대기 아님). 그리고 그 판이 map-tree 요청이면
  「Main Quiz 이어서 만들기」 아래에 「새로 출제 (처음부터)」 버튼이 보인다. 두 버튼은 같은 이유 칸을 쓴다.
  이유가 비어 있으면 두 버튼 모두 막힌다.
- R2 새로 출제 요청 본문은 새 요청 기본값(`map-tree/3`, source, cli)에 새 requestId와 `restart: true`, `resume: false`,
  `resumeReason: <이유>`를 더한다. 공개 범위는 옛 판의 `privatePilot`를 그대로 쓴다(화면 문구 「같은 공개 범위」).
- R3 서버는 `restart: true`일 때 같은 입력의 기존 판을 재사용하지 않는다. 그 강의의 최근 판(정규화된 원본)을 `restartOf`로,
  이유를 `restartReason`으로 입력에 넣는다. 그래서 입력 지문이 달라지고, 새 생성 ID·새 job으로 등록된다.
- R4 서버 거절:
  `restart`와 `resume`을 함께 보냄 → 422. pipeline 없음 → 422. 이유 없음 → 422.
  최근 판 없음 → 409. 최근 판이 공개됨·진행 중·대기·웹 응답 대기 → 409. 요청자가 최근 판 소유자가 아님 → 409.
  공개된 Main-Quiz 판이 있음 → 409(기존). 다른 문제은행 작업이 열려 있음 → 409(기존).
- R5 같은 requestId로 다시 보내면 첫 응답의 판을 돌려준다(기존 멱등성). 새 판을 하나 더 만들지 않는다.
- R6 새로 출제한 판이 다시 실패하면 그 판을 대상으로 다시 「이어서 만들기」·「새로 출제」를 할 수 있다(사슬).

## 책임·입출력 계약·오류 상태
| 구성 | 변경 | 계약 |
|---|---|---|
| server `routes/root_generation.py` | `RequestIn.restart: bool = False`. restart 분기는 requestId 재사용 확인 **뒤**, 지문 계산 **전**. `generation_input`에 `restartOf` 추가 | 요청 본문 필드 1개 추가. 응답 `generation.restartOf` 추가 |
| web `bank/RootGenerationPanel.tsx` | 두 번째 버튼, 이유 칸 라벨, 안내 문장 | 위 요청 본문 |
| runner·생성기·계약 | 변경 없음 | `restartOf`·`restartReason`은 서버 packet의 일반 키다. packet_hash에 들어가고 derive_packet이 그대로 복사한다. 러너 재설치 불필요 |

## 호환성과 데이터 보존
- DB 스키마·migration 없음. `root_generation.packet` JSON에 키 2개가 추가될 뿐이다.
- 옛 판은 행·job 상태·`runs/_root-generation/<옛 id>`·이어 하기 이유를 하나도 바꾸지 않는다.
- 옛 packet에는 `restartOf`가 없다. `generation_input`에서 None이 되므로 기존 중복 판정·`canonical_generation`·`retain_duplicate`는 그대로다.
- 학습 기록·공개된 판·다른 강의는 건드리지 않는다. 공개된 판의 교체 거절은 그대로다.

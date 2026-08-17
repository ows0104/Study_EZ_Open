# Study_EZ 예습 브리지

작년 필기와 예습 프롬프트를 **ChatGPT 새 대화에 직접 채우고**, 만들어진 공유
링크를 강의에 되돌려 주는 크롬 확장입니다.

웹페이지는 남의 사이트에 파일을 첨부할 수 없습니다. 그래서 이것이 없으면 학생이
직접 PDF를 내려받아 첨부하고 프롬프트를 붙여넣어야 하고, 만든 대화의 링크도
손으로 옮겨 적어야 합니다. 이 확장은 그 셋을 없앱니다.

MedDeck AI Bridge에서 갈라져 나왔습니다. 거기는 Claude·Gemini·ChatGPT 셋을
다루지만 여기는 ChatGPT만 봅니다 — `preview.provider`의 기본값이고, Pre-Quiz가
읽는 것도 ChatGPT 공유 페이지입니다.

## 설치

1. Chrome에서 `chrome://extensions`를 엽니다.
2. 오른쪽 위 **개발자 모드**를 켭니다.
3. **압축해제된 확장 프로그램을 로드합니다**를 누릅니다.
4. 이 `chrome-extension` 폴더를 고릅니다.
5. Study_EZ 탭을 새로고침합니다.

소스를 고친 뒤에는 `chrome://extensions`의 카드에서 새로고침을 누르고 Study_EZ
탭도 새로고침해야 합니다.

## 어떻게 도는가

```
Study_EZ 패널에서 "예습 시작하기"
  └ 웹앱이 서명 URL을 받아 STUDYEZ_OPEN_PREVIEW를 postMessage
      └ studyez-bridge.js → background.js
          ├ 자료 주소를 허용 목록으로 검사 (R2 또는 로컬 산출물 경로만)
          └ ChatGPT 새 탭을 열고 자료를 세션 저장소에 넣음
              └ chatgpt-bridge.js가 확인 카드를 띄움
                  ├ 배경이 PDF를 받아 조각으로 넘김
                  ├ input[type=file]에 DataTransfer로 첨부
                  └ 입력창에 프롬프트 삽입 — **전송은 사람이 누름**
                      └ 대화 주소가 생기면 background가 잡아 웹앱에 되돌림
                          └ chatgpt-share.js가 답이 끝나기를 기다렸다 공유 링크 생성
                              └ 웹앱이 저장 → 확장에 확인 → 대기 목록에서 삭제
```

**저장 확인이 오기 전에는 링크를 지우지 않습니다.** 탭이 닫혔거나 잠들어 전달이
실패해도 다음 기회에 다시 보냅니다.

## 두 가지 링크

`preview` 표의 두 칸에 1:1로 들어갑니다.

| 종류 | 저장되는 칸 | 누가 열 수 있나 |
|---|---|---|
| `chatgpt` | `conversation_url` | 만든 계정만 |
| `chatgpt_share` | `share_url` | 링크를 가진 누구나. **Pre-Quiz의 재료** |

대화 주소만으로는 반 친구에게 죽은 링크입니다. 공유 링크를 따로 만드는 이유가
그것이고, `studyez preview`가 읽는 것도 이쪽입니다.

**저장은 관리자만 성공합니다.** 서버의 `PUT …/preview`가 러너·관리자 게이트 뒤에
있습니다. 일반 사용자도 예습 대화는 똑같이 열리고, 링크가 덱의 재료로 남지 않을
뿐입니다.

## 보안 범위

- Study_EZ 주소에서 온 요청만 받습니다 (`background.js`의 `WEBAPP_ORIGINS`).
- 자료는 서명된 R2 주소나 로컬 테스트 서버의 `/api/local-storage/lectures/` 아래에서만
  내려받습니다. 웹앱이 시키는 주소로 fetch하므로 이 허용 목록이 유일한 관문입니다.
- 공유 링크는 감시 기록에 적힌 강의에만 붙습니다. 페이지가 아무 강의에나 링크를
  달 수 없습니다.
- 검색 노출(`is_discoverable`)은 끕니다. 링크 밖으로 새지 않습니다.
- **전송 버튼은 사람이 직접 누릅니다.**

## 어느 주소에서 도는가

```
https://study-ez-open.pages.dev    배포
http://localhost:5173              로컬 개발
```

주소가 늘면 **두 곳을 같이** 고칩니다. 한쪽만 고치면 콘텐츠 스크립트는 붙는데
배경이 요청을 안 받거나, 그 반대가 됩니다.

- `manifest.json`의 `content_scripts[0].matches`
- `background.js`의 `WEBAPP_ORIGINS`

## 계약

메시지 이름은 `web/src/bridge/protocol.ts`가 정의하고 `protocol.js`가 그 사본입니다.
한쪽만 고치면 조용히 끊깁니다.

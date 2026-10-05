# 공용 세션 코드

Study_EZ와 Spotter가 함께 사용하는 로그인 세션 코드다.
현재 공용 원본은 `session/session.js` 하나다.

| 사용하는 곳 | 연결 방식 |
|---|---|
| `web/src/supabase.ts` | Vite import |
| `spotter/web/session.js` | 정적 앱용 사본 |

`Domain=.studyez.kr` 쿠키로 형제 서브도메인이 세션을 공유한다.
쿠키를 사용할 수 없는 환경에서는 각 앱의 localStorage로 돌아간다.

원본을 수정한 뒤 Spotter 사본을 동기화하고 검사한다.

```powershell
python spotter/scripts/sync_shared.py
python spotter/scripts/sync_shared.py --check
```

공유 모듈은 두 앱이 실제로 사용하는 코드만 둔다.
과거 족보·업로드·품질 코드를 합치지 않은 이유는
[통합 검토 기록](../docs/archive/refactor-plan.md)에 있다.
앱별 권한과 도메인 연결은 [형제 앱 안내](../docs/sibling-apps.md)를 본다.

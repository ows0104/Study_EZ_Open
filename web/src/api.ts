import { LOCAL_TEST_TOKEN } from "./localTest";
import { auth } from "./supabase";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function authHeader(): Promise<Record<string, string>> {
  if (LOCAL_TEST_TOKEN) return { Authorization: `Bearer ${LOCAL_TEST_TOKEN}` };
  const { data } = (await auth?.getSession()) ?? { data: { session: null } };
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(await authHeader()),
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(response.status, typeof detail === "string" ? detail : "요청이 실패했습니다.");
  }
  return payload as T;
}

/**
 * 파일을 바로 받는다.
 *
 * `openSignedFile`과 달리 탭을 열지 않는다. 덱은 보는 것이 아니라 받는 것이라
 * 빈 탭이 하나 남는 것이 방해가 된다.
 *
 * 서버가 자산 URL에 `Content-Disposition: attachment`를 실어 보내므로 링크를
 * 누르는 것만으로 내려받는다. `download` 속성은 같은 출처일 때만 듣지만,
 * 다른 출처(R2)에서는 그 헤더가 대신 일을 한다.
 */
export async function downloadSignedFile(path: string, filename: string): Promise<void> {
  const { url } = await api<{ url: string }>(path);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noreferrer";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}

/**
 * 파일을 새 탭에서 연다.
 *
 * 서명 URL은 수명이 분 단위라 화면을 그릴 때 미리 받아 둘 수 없다. 누른
 * 순간에 받아서 바로 연다.
 *
 * `window.open`을 먼저 부르고 나중에 주소를 채우는 이유는, await 뒤에 부르면
 * 사용자 제스처와 끊겨 팝업 차단에 걸리기 때문이다.
 *
 * **`noopener`를 features에 주면 안 된다.** 그러면 `window.open`이 핸들이 아니라
 * `null`을 돌려준다(명세다). 그 `null`을 "팝업이 막혔다"로 읽고 있어서, 누를
 * 때마다 빈 탭이 하나 열리고 **보던 탭이 파일로 바뀌었다** — 캘린더가 사라지는
 * 것이 실제 증상이었다. 핸들을 받아 두고 `opener`는 직접 끊는다.
 *
 * **주소에 `?inline=1`을 붙여야 정말 열린다.** 안 붙이면 서버가 첨부로
 * 서명해 주고, 그러면 탭이 뜨자마자 내려받기로 바뀌며 빈 탭만 남는다.
 */
export async function openSignedFile(path: string): Promise<void> {
  const tab = window.open("", "_blank");
  if (tab) {
    // 새 탭이 우리 window를 되짚지 못하게 한다. `noopener`가 하던 일이다.
    try {
      tab.opener = null;
    } catch {
      // 막혀도 그만이다. 곧 다른 출처로 넘어가면 어차피 끊긴다.
    }
  }
  try {
    const { url } = await api<{ url: string }>(path);
    if (tab) {
      // `replace`라서 빈 about:blank가 그 탭의 뒤로 가기에 남지 않는다.
      tab.location.replace(url);
      return;
    }
    // 팝업이 정말 막힌 경우. 그래도 보던 탭은 건드리지 않는다 — 파일 하나
    // 열자고 캘린더를 잃는 것이 더 나쁘다.
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  } catch (error) {
    tab?.close();
    throw error;
  }
}

/**
 * 파일을 **읽어서** 받는다. 저장하는 것이 아니라 코드가 쓰려는 바이트다.
 *
 * `downloadSignedFile`과 하는 일이 다르다. 저쪽은 서명 URL을 받아 링크를 눌러
 * 브라우저에게 맡기고 — 그러면 바이트가 우리 코드에 안 들어온다. 덱을 합치려면
 * 들어와야 한다(`bundle/apkg.ts`).
 *
 * **그래서 R2가 아니라 서버를 부른다.** 서명 URL을 `fetch`로 읽으려면 R2 쪽에
 * CORS가 있어야 하는데 지금은 없다(2026-09-15 실측). `<a>`와 `<img>`는 CORS를
 * 안 타므로 이 저장소의 다른 자리는 여기 안 걸렸다. 사정은
 * `server/app/routes/bundles.py` 첫머리에 있다.
 */
export async function apiBytes(path: string): Promise<Uint8Array> {
  const response = await fetch(`${BASE}${path}`, { headers: await authHeader() });
  if (!response.ok) {
    // 본문이 JSON이 아닐 수 있다(스트리밍 경로라 프록시가 끼어들면 HTML이 온다).
    // 읽다 죽으면 상태 코드마저 잃으므로 감싼다.
    let detail = "";
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? "";
    } catch {
      detail = "";
    }
    throw new ApiError(response.status, detail || "파일을 받지 못했습니다.");
  }
  return new Uint8Array(await response.arrayBuffer());
}

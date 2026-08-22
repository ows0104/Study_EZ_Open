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
 * 파일을 새 탭에서 연다.
 *
 * 서명 URL은 수명이 분 단위라 화면을 그릴 때 미리 받아 둘 수 없다. 누른
 * 순간에 받아서 바로 연다.
 *
 * `window.open`을 먼저 부르고 나중에 주소를 채우는 이유는, await 뒤에 부르면
 * 사용자 제스처와 끊겨 팝업 차단에 걸리기 때문이다.
 */
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

export async function openSignedFile(path: string): Promise<void> {
  const tab = window.open("", "_blank", "noopener,noreferrer");
  try {
    const { url } = await api<{ url: string }>(path);
    if (tab) tab.location.href = url;
    else window.location.href = url;
  } catch (error) {
    tab?.close();
    throw error;
  }
}

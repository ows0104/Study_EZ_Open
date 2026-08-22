import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/**
 * 자산은 `pages.dev`에서 받는다.
 *
 * `studyez.kr`는 Cloudflare **Free** 존이고, 한국에서 온 요청이 서울이 아니라
 * **로스앤젤레스**에서 응답한다. 같은 기계에서 같은 순간에 잰 값이다:
 *
 *   studyez.kr             colo=LAX   JS 146KB 수신 0.89s
 *   study-ez-open.pages.dev colo=ICN   같은 파일        0.14s
 *   www.cloudflare.com     colo=ICN   (대조군)
 *
 * `/cdn-cgi/trace`는 셋 다 `loc=KR`을 준다 — 우리 쪽 네트워크가 아니라 **존의
 * 성질**이다. Cloudflare API로 확인한 플랜은 `Free Website`이고, `pages.dev`는
 * Cloudflare 자기 도메인이라 이 제한을 안 받는다.
 *
 * 그래서 문서는 `studyez.kr`에서 주고(주소는 그대로 브랜드 도메인이다) 무거운
 * 자산만 `pages.dev`에서 받는다. 같은 Pages 배포라 둘이 어긋날 수 없고,
 * Pages가 `Access-Control-Allow-Origin: *`를 실어 줘서 모듈 스크립트가 통과한다.
 *
 * **플랜을 올려 apex가 ICN에서 오게 되면 이 우회는 필요 없다.** 그때는
 * `VITE_ASSET_ORIGIN=/`로 빌드하면 원래대로 같은 출처에서 받는다.
 */
const ASSET_ORIGIN = "https://study-ez-open.pages.dev/";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    plugins: [react()],
    // 개발 서버는 언제나 자기 출처다 — 여기서 배포본 자산을 받아 오면 지금 고친
    // 것이 화면에 안 나온다.
    base: command === "build" ? env.VITE_ASSET_ORIGIN || ASSET_ORIGIN : "/",
    server: {
      port: 5173,
      // 개발 중에는 같은 출처로 보내 CORS를 신경 쓰지 않는다. 배포에서는
      // VITE_API_BASE_URL이 채워지고 이 프록시는 쓰이지 않는다.
      proxy: {
        "/api": { target: process.env.VITE_DEV_API ?? "http://localhost:8000", changeOrigin: true },
      },
    },
  };
});

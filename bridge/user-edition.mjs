/**
 * 학생용 사용자판으로 바꾼다. 학생에게 나가는 ZIP 둘이 같이 쓴다:
 * 스토어 ZIP(`build-store-package.ps1`)과 사이트 ZIP(`../web/scripts/pack-extension.mjs`).
 *
 * 사용자판은 `EDITION: "user"`라 개인 예습·복습의 수동입력만 연다(배경이 자동전송·공유·bank를 거절).
 * 관리자 Quiz Bank 파일 회수 스크립트는 넣지 않는다. 관리자판은 이 폴더 그대로다.
 *
 * 모듈: `toUserEdition(files)` — 파일 이름 → Buffer|string 의 Map을 받아 바뀐 Map을 돌려준다.
 * 명령: `node user-edition.mjs <폴더>` — 그 폴더의 파일을 제자리에서 바꾼다.
 */
import { existsSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ADMIN_ONLY_FILES = ["bank-file.js", "bank-download.js"];
const ADMIN_IMPORTS = 'importScripts("protocol.js", "bank-file.js", "bank-download.js");';
const USER_IMPORTS = 'importScripts("protocol.js");';
const FULL = 'EDITION: "full",';
const USER = 'EDITION: "user",';

const text = (value) => (typeof value === "string" ? value : value.toString("utf8"));

export function toUserEdition(files) {
  const protocol = text(files.get("protocol.js"));
  if (protocol.split(FULL).length !== 2) throw new Error("protocol.js에서 EDITION 표시를 찾지 못했습니다.");
  const background = text(files.get("background.js"));
  if (!background.startsWith(ADMIN_IMPORTS)) throw new Error("background.js 첫 줄의 importScripts가 예상과 다릅니다.");
  const manifest = JSON.parse(text(files.get("manifest.json")));
  for (const script of manifest.content_scripts) {
    script.js = script.js.filter((name) => !ADMIN_ONLY_FILES.includes(name));
  }

  const result = new Map(files);
  for (const name of ADMIN_ONLY_FILES) result.delete(name);
  result.set("protocol.js", protocol.replace(FULL, USER));
  result.set("background.js", USER_IMPORTS + background.slice(ADMIN_IMPORTS.length));
  result.set("manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);

  // 서비스 워커·콘텐츠 스크립트가 읽는 파일이 하나라도 없으면 확장 전체가 시작하지 못한다.
  const referenced = new Set([manifest.background.service_worker, "protocol.js",
    ...manifest.content_scripts.flatMap((script) => script.js)]);
  const missing = [...referenced].filter((name) => !result.has(name));
  if (missing.length) throw new Error(`사용자판에 실행 파일이 빠졌습니다: ${missing.join(", ")}`);
  return result;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = resolve(process.argv[2] || "");
  if (!process.argv[2] || !statSync(directory).isDirectory()) throw new Error("사용법: node user-edition.mjs <폴더>");
  const files = new Map(readdirSync(directory).filter((name) => name.endsWith(".js") || name === "manifest.json")
    .map((name) => [name, readFileSync(join(directory, name))]));
  const result = toUserEdition(files);
  for (const name of files.keys()) {
    if (!result.has(name) && existsSync(join(directory, name))) rmSync(join(directory, name));
  }
  for (const name of ["protocol.js", "background.js", "manifest.json"]) {
    writeFileSync(join(directory, name), result.get(name), "utf8");
  }
}

/**
 * `bridge/`을 `public/`의 zip 하나로 묶는다.
 *
 * 사용자는 저장소를 갖고 있지 않으므로 "폴더를 고르세요"라고 말할 수 없다.
 * 웹앱이 직접 내려주면 화면에서 설치까지 한 줄로 이어진다.
 *
 * 의존성을 하나 더 들이지 않으려고 zip을 직접 쓴다. 압축 없이(store 0) 담으면
 * 형식이 아주 단순하고, 확장 소스는 몇십 KB라 줄여서 얻을 것도 없다.
 */

import { createHash } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { crc32 } from "node:zlib";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../../bridge");
const target = resolve(here, "../public/studyez-extension.zip");
// 설치 표시는 웹의 최소 버전 검사에 쓰인다. 패키지와 다르면 배포하지 않는다.
const manifest = JSON.parse(readFileSync(resolve(source, "manifest.json"), "utf8"));
const protocol = readFileSync(resolve(source, "protocol.js"), "utf8");
const advertisedVersion = /VERSION:\s*"([^"]+)"/.exec(protocol)?.[1];
if (advertisedVersion !== manifest.version) {
  throw new Error(`확장 버전 불일치: manifest=${manifest.version}, protocol=${advertisedVersion}`);
}

/** 배포에 들어갈 것만. 스토어 자산과 문서는 뺀다. */
const SKIP = new Set(["store-assets", "release", "node_modules", ".git"]);

function collect(directory, base = directory) {
  const entries = [];
  for (const name of readdirSync(directory).sort()) {
    if (SKIP.has(name)) continue;
    const full = join(directory, name);
    if (statSync(full).isDirectory()) entries.push(...collect(full, base));
    else entries.push({ name: relative(base, full).replaceAll("\\", "/"), body: readFileSync(full) });
  }
  return entries;
}

/**
 * 시각을 고정한다. 같은 소스면 같은 바이트가 나와야 배포가 매번 새 파일을
 * 만들지 않는다.
 */
const DOS_TIME = 0;
const DOS_DATE = 0x21 << 5; // 1980-01-01

function localHeader(entry) {
  const name = Buffer.from(entry.name, "utf8");
  const head = Buffer.alloc(30);
  head.writeUInt32LE(0x04034b50, 0);
  head.writeUInt16LE(20, 4); // version
  head.writeUInt16LE(0x0800, 6); // UTF-8 파일명
  head.writeUInt16LE(0, 8); // store
  head.writeUInt16LE(DOS_TIME, 10);
  head.writeUInt16LE(DOS_DATE, 12);
  head.writeUInt32LE(entry.crc, 14);
  head.writeUInt32LE(entry.body.length, 18);
  head.writeUInt32LE(entry.body.length, 22);
  head.writeUInt16LE(name.length, 26);
  head.writeUInt16LE(0, 28);
  return Buffer.concat([head, name, entry.body]);
}

function centralHeader(entry) {
  const name = Buffer.from(entry.name, "utf8");
  const head = Buffer.alloc(46);
  head.writeUInt32LE(0x02014b50, 0);
  head.writeUInt16LE(20, 4);
  head.writeUInt16LE(20, 6);
  head.writeUInt16LE(0x0800, 8);
  head.writeUInt16LE(0, 10);
  head.writeUInt16LE(DOS_TIME, 12);
  head.writeUInt16LE(DOS_DATE, 14);
  head.writeUInt32LE(entry.crc, 16);
  head.writeUInt32LE(entry.body.length, 20);
  head.writeUInt32LE(entry.body.length, 24);
  head.writeUInt16LE(name.length, 28);
  head.writeUInt32LE(entry.offset, 42);
  return Buffer.concat([head, name]);
}

const files = collect(source);
if (!files.some((file) => file.name === "manifest.json")) {
  throw new Error(`manifest.json이 없습니다: ${source}`);
}

let offset = 0;
const locals = [];
for (const file of files) {
  file.crc = crc32(file.body) >>> 0;
  file.offset = offset;
  const block = localHeader(file);
  locals.push(block);
  offset += block.length;
}

const centrals = files.map(centralHeader);
const centralSize = centrals.reduce((total, block) => total + block.length, 0);
const end = Buffer.alloc(22);
end.writeUInt32LE(0x06054b50, 0);
end.writeUInt16LE(files.length, 8);
end.writeUInt16LE(files.length, 10);
end.writeUInt32LE(centralSize, 12);
end.writeUInt32LE(offset, 16);

const zip = Buffer.concat([...locals, ...centrals, end]);
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, zip);

const digest = createHash("sha256").update(zip).digest("hex").slice(0, 12);
console.log(`확장 ${files.length}개 파일 → public/studyez-extension.zip (${(zip.length / 1024).toFixed(1)}KB, ${digest})`);

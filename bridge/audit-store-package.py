"""Chrome Web Store ZIP의 구조·권한·실행 코드 범위를 재현 가능하게 검사한다."""

from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
ZIP = ROOT / "release" / f"studyez-preview-bridge-{SOURCE_MANIFEST['version']}-web-store.zip"
EXPECTED = {
    "manifest.json",
    "background.js",
    "protocol.js",
    "studyez-bridge.js",
    "chatgpt-bridge.js",
    "chatgpt-share.js",
    "provider-share.js",
    "icons/icon-16.png",
    "icons/icon-32.png",
    "icons/icon-48.png",
    "icons/icon-128.png",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


raw = ZIP.read_bytes()
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    names = set(archive.namelist())
    require(names == EXPECTED, f"unexpected entries: {sorted(names ^ EXPECTED)}")
    manifest_text = archive.read("manifest.json").decode("utf-8")
    manifest = json.loads(manifest_text)

    require(manifest["manifest_version"] == 3, "Manifest V3가 아닙니다.")
    require(manifest["name"] == "Study EZ 예습 브리지", "확장 이름이 다르거나 UTF-8이 깨졌습니다.")
    require(manifest["version"] == SOURCE_MANIFEST["version"], "스토어 버전이 소스 manifest와 다릅니다.")
    require(manifest["permissions"] == ["storage", "scripting"], "storage·scripting 외 권한이 있습니다.")
    require(
        manifest["host_permissions"]
        == [
            "https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/*",
            "https://chatgpt.com/*",
            "https://gemini.google.com/*",
            "https://claude.ai/*",
            "https://g.co/gemini/share/*",
        ],
        "호스트 권한이 최소 허용 목록과 다릅니다.",
    )
    require(manifest["content_scripts"][0]["matches"] == ["https://studyez.kr/*"], "Study EZ match가 다릅니다.")
    require(
        manifest["content_scripts"][1]["matches"]
        == ["https://chatgpt.com/*", "https://gemini.google.com/*", "https://claude.ai/*"],
        "AI 입력 브리지 match가 다릅니다.",
    )
    require(manifest["content_scripts"][2]["matches"] == ["https://chatgpt.com/*"], "ChatGPT match가 다릅니다.")
    require(
        manifest["content_scripts"][3]["matches"] == ["https://gemini.google.com/*", "https://claude.ai/*"],
        "Gemini·Claude 링크 감시 match가 다릅니다.",
    )
    require("localhost" not in manifest_text and "127.0.0.1" not in manifest_text, "manifest에 로컬 주소가 있습니다.")
    background_text = archive.read("background.js").decode("utf-8")
    referenced = {manifest["background"]["service_worker"]}
    for call in re.findall(r"(?m)^importScripts\(([^)]*)\)", background_text):
        referenced.update(re.findall(r'"([^"]+)"', call))
    for script in manifest["content_scripts"]:
        referenced.update(script["js"])
    require(referenced <= names, f"실행에 필요한 파일이 ZIP에 없습니다: {sorted(referenced - names)}")
    # 스토어판은 학생용 사용자판이다. 관리자 Quiz Bank 파일 회수 코드와 자동전송·공유·bank 요청을 열지 않는다.
    require(not any(name.startswith("bank-") for name in referenced | names), "관리자 bank 스크립트가 스토어판에 있습니다.")
    protocol_text = archive.read("protocol.js").decode("utf-8")
    require(protocol_text.count('EDITION: "user",') == 1 and 'EDITION: "full"' not in protocol_text, "스토어판 EDITION이 user가 아닙니다.")
    require('EDITION === "user" && (mode === "shared" || mode === "bank" || payload.autoSend === true)' in background_text,
            "사용자판의 자동전송·공유·bank 거절 분기가 없습니다.")

    scripts = [name for name in names if name.endswith(".js")]
    script_text = "\n".join(archive.read(name).decode("utf-8") for name in scripts)
    require(not any(value in script_text for value in ("eval(", "new Function", "WebAssembly.instantiate", "WebAssembly.compile")), "동적 코드 실행이 있습니다.")
    require("import(" not in script_text, "동적 import가 있습니다.")
    require("localhost" not in script_text and "127.0.0.1" not in script_text, "실행 코드에 로컬 개발 주소가 있습니다.")
    bridge_text = archive.read("chatgpt-bridge.js").decode("utf-8")
    require(
        all(
            marker in bridge_text
            for marker in (
                'const CONSENT_KEY = "studyez-consent:"',
                "chrome.storage.local.get",
                "chrome.storage.local.set",
                "chrome.storage.local.remove",
                'data-action="revoke"',
            )
        ),
        "모드별 동의 기억 또는 해제 코드가 ZIP에 빠졌습니다.",
    )
    expected_background = (ROOT / "background.js").read_text(encoding="utf-8")
    expected_background = expected_background.replace(', "http://localhost:5173"', "")
    expected_background = re.sub(
        r"(?m)^    const localOrigins = .*?\r?\n    return localOrigins.*?;\r?$",
        "    return false;",
        expected_background,
    )
    import_line = 'importScripts("protocol.js", "bank-file.js", "bank-download.js");'
    require(expected_background.startswith(import_line), "소스 background.js 첫 줄이 예상과 다릅니다.")
    expected_background = 'importScripts("protocol.js");' + expected_background[len(import_line):]
    expected_protocol = (ROOT / "protocol.js").read_text(encoding="utf-8").replace('EDITION: "full",', 'EDITION: "user",')
    transformed = {"background.js": expected_background.encode(), "protocol.js": expected_protocol.encode()}
    expected_scripts = {name: transformed.get(name) or (ROOT / name).read_bytes() for name in scripts}
    require(
        all(hashlib.sha256(expected_scripts[name]).digest() == hashlib.sha256(archive.read(name)).digest() for name in scripts),
        "ZIP의 실행 코드가 검사한 소스 및 스토어 변환 결과와 다릅니다.",
    )

    for size in (16, 32, 48, 128):
        icon = archive.read(f"icons/icon-{size}.png")
        require(icon.startswith(b"\x89PNG\r\n\x1a\n") and len(icon) >= 26, f"icon-{size}.png가 PNG가 아닙니다.")
        width, height = struct.unpack(">II", icon[16:24])
        color_type = icon[25]
        require((width, height) == (size, size) and color_type == 6, f"icon-{size}.png 형식이 잘못됐습니다.")

    urls = sorted(set(re.findall(r"https?://[^\"'\s)]+", script_text)))

print(f"OK: {ZIP}")
print(f"SHA256: {hashlib.sha256(raw).hexdigest()}")
print(f"entries: {len(EXPECTED)}")
print("edition: user (manual personal preview/review only; no auto-send, shared links, or Quiz Bank)")
print("permissions: storage, scripting")
print("consent: remembered per mode with local revoke")
print("host permissions: exact R2 origin, ChatGPT, Gemini, Claude, Gemini short links")
print(f"runtime URLs: {urls}")

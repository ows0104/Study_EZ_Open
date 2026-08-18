"""Chrome Web Store ZIP의 구조·권한·실행 코드 범위를 재현 가능하게 검사한다."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from PIL import Image


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
    require(manifest["permissions"] == ["storage"], "storage 외 권한이 있습니다.")
    require(
        manifest["host_permissions"]
        == [
            "https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/*",
            "https://chatgpt.com/*",
        ],
        "호스트 권한이 최소 허용 목록과 다릅니다.",
    )
    require(manifest["content_scripts"][0]["matches"] == ["https://studyez.kr/*"], "Study EZ match가 다릅니다.")
    require(manifest["content_scripts"][1]["matches"] == ["https://chatgpt.com/*"], "ChatGPT match가 다릅니다.")
    require("localhost" not in manifest_text and "127.0.0.1" not in manifest_text, "manifest에 로컬 주소가 있습니다.")

    scripts = [name for name in names if name.endswith(".js")]
    script_text = "\n".join(archive.read(name).decode("utf-8") for name in scripts)
    require(not any(value in script_text for value in ("eval(", "new Function", "WebAssembly.instantiate", "WebAssembly.compile")), "동적 코드 실행이 있습니다.")
    require("import(" not in script_text, "동적 import가 있습니다.")
    require("localhost" not in script_text and "127.0.0.1" not in script_text, "실행 코드에 로컬 개발 주소가 있습니다.")
    expected_background = (ROOT / "background.js").read_text(encoding="utf-8")
    expected_background = expected_background.replace(', "http://localhost:5173"', "")
    expected_background = re.sub(
        r"(?m)^    const localOrigins = .*?\r?\n    return localOrigins.*?;\r?$",
        "    return false;",
        expected_background,
    )
    expected_scripts = {
        name: expected_background.encode() if name == "background.js" else (ROOT / name).read_bytes()
        for name in scripts
    }
    require(
        all(hashlib.sha256(expected_scripts[name]).digest() == hashlib.sha256(archive.read(name)).digest() for name in scripts),
        "ZIP의 실행 코드가 검사한 소스 및 스토어 변환 결과와 다릅니다.",
    )

    for size in (16, 32, 48, 128):
        with Image.open(io.BytesIO(archive.read(f"icons/icon-{size}.png"))) as icon:
            require(icon.mode == "RGBA" and icon.size == (size, size), f"icon-{size}.png 형식이 잘못됐습니다.")

    urls = sorted(set(re.findall(r"https?://[^\"'\s)]+", script_text)))

print(f"OK: {ZIP}")
print(f"SHA256: {hashlib.sha256(raw).hexdigest()}")
print(f"entries: {len(EXPECTED)}")
print("permissions: storage")
print("host permissions: exact R2 origin, chatgpt.com")
print(f"runtime URLs: {urls}")

"""Run the isolated local block-transition fixture in a fresh headless browser."""
import html
import os
import re
import subprocess
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[3]
browser = Path(os.environ.get("CHROME_PATH", "C:/Program Files/Google/Chrome/Application/chrome.exe"))
profile = root / "runs/_development/2026-11-01-block-auto-deploy" / f"browser-{uuid.uuid4().hex}"
profile.mkdir(parents=True)
command = [str(browser), "--headless=new", "--disable-gpu", "--disable-background-networking",
           "--disable-component-update", "--no-first-run", "--no-default-browser-check",
           f"--user-data-dir={profile}", "--dump-dom", "--timeout=15000", "--virtual-time-budget=75000",
           "http://127.0.0.1:5197/tests/study-block-transition.html"]
result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=45, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
match = re.search(r'<output id="result" data-status="([^"]+)">(.*?)</output>', result.stdout, re.S)
if not match:
    (profile.parent / "browser-diagnostic.html").write_text(result.stdout, encoding="utf-8")
    (profile.parent / "browser-diagnostic.log").write_text(result.stderr, encoding="utf-8")
    raise SystemExit(f"Browser fixture did not produce results (exit {result.returncode}, stdout {len(result.stdout)} bytes)")
print(match.group(1), html.unescape(match.group(2)))
if result.returncode or match.group(1) != "passed":
    raise SystemExit(1)

"""Report failures and publish bank artifacts after processing. No model execution."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import transport
from . import state


def _upload_slides(client: transport.Client, subject: str, run_id: str, slides: list[Path]) -> int:
    if not slides:
        return 0
    base = transport.lecture_path(subject, run_id)
    uploads = [transport.Upload("bank_media", p) for p in slides]
    payloads = [u.payload() for u in uploads]
    signed = client.call("POST", f"{base}/uploads", payloads)
    urls = {e["filename"]: e["uploadUrl"] for e in signed["files"]}
    missing = set(client.call("POST", f"{base}/uploads/complete", payloads).get("missing", []))
    todo = [u for u in uploads if u.filename in missing]
    for upload in todo:
        transport._put_with_retry(client, urls[upload.filename], upload)
    if todo:
        left = client.call("POST", f"{base}/uploads/complete", [u.payload() for u in todo]).get("missing", [])
        if left:
            raise transport.PublishError(f"올렸는데 서버가 못 찾는다: {', '.join(left[:5])}")
    return len(todo)


def report_failure(client: transport.Client, base: str, got: dict, why: str, *, revision: dict | None = None) -> int:
    responded = got["respondedAt"]
    maintenance = got.get("existingBank") is not None
    try:
        client.call("PUT", f"{base}/bank", {"respondedAt": responded, "message": why,
                    **({"revision": revision} if revision is not None else {}),
                    **({"baseBuildId": got["baseBuildId"]} if maintenance else {})})
    except transport.PublishError as e:
        print(f"  (실패를 서버에 적지 못했다: {e})", flush=True)
    print(f"멈췄다 — {why}", flush=True)
    return 1


def publish_result(client: transport.Client, subject: str, run_id: str, got: dict,
                   out: Path, result: dict, *, revision: dict | None = None) -> int:
    base = transport.lecture_path(subject, run_id)
    responded = got["respondedAt"]
    maintenance = got.get("existingBank") is not None
    generation_usage = []
    upload_started = time.monotonic()
    slides = sorted((out / "slides").glob("*.png")) if (out / "slides").is_dir() else []
    sent = _upload_slides(client, subject, run_id, slides)
    image_seconds = time.monotonic() - upload_started
    usage = [json.loads(line) for line in (out / "usage.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()] if (out / "usage.jsonl").is_file() else []
    answer = client.call("PUT", f"{base}/bank", {
        "respondedAt": responded, "bank": state._read(out / "bank.json"), "validation": state._read(out / "validation.json"),
        'allowUnresolved': True,
        **({'revision': revision} if revision is not None else {}),
        **({"baseBuildId": got["baseBuildId"]} if maintenance else {}),
        "review": state._read(out / "review.json"), "pages": state._read(out / "pages.json") or {}, "usage": generation_usage + usage,
        "message": ('미해결 검수 지적을 보존하고 게시했습니다.' if revision else '')
            if result.get('publication', {}).get('allowed') else ("" if result["pass"] else f"검증 오류 {result['errors']}건")})
    upload_timing = {'imageUploadSeconds': round(image_seconds, 2),
                     'totalSeconds': round(time.monotonic() - upload_started, 2), 'newImages': sent}
    (out / 'upload-timings.json').write_text(json.dumps(upload_timing), encoding='utf-8')
    print(f"  이미지 업로드 {image_seconds:.1f}초 · 전체 업로드 {upload_timing['totalSeconds']:.1f}초", flush=True)
    print(f"Quiz Bank {run_id}: {answer.get('status')} · 문항 {result['questions']} · 검토 {result['review']}"
          f" · 슬라이드 {len(slides)}장(새로 {sent})", flush=True)
    return 0

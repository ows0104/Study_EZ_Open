from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "bridge"
sys.path.insert(0, str(ROOT / "server"))

from app.preview_links import conversation_url, share_url  # noqa: E402


class ExtensionProviderTests(unittest.TestCase):
    def test_manifest_covers_all_preview_providers(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        hosts = set(manifest["host_permissions"])
        self.assertTrue({
            "https://chatgpt.com/*",
            "https://gemini.google.com/*",
            "https://claude.ai/*",
        } <= hosts)
        scripts = {item for block in manifest["content_scripts"] for item in block["js"]}
        self.assertTrue({"chatgpt-bridge.js", "chatgpt-share.js", "provider-share.js"} <= scripts)

    def test_web_and_extension_link_kinds_do_not_drift(self) -> None:
        web = (ROOT / "web" / "src" / "bridge" / "protocol.ts").read_text(encoding="utf-8")
        extension = (EXTENSION / "protocol.js").read_text(encoding="utf-8")
        expected = {
            "chatgpt", "chatgpt_share", "gemini", "gemini_share", "claude", "claude_share",
            "chatgpt_review", "gemini_review", "claude_review",
            "chatgpt_bank", "chatgpt_bank_share",
        }
        web_block = re.search(r"export const LINK_KINDS = \[(.*?)\] as const", web, re.S)
        extension_block = re.search(r"LINK_KINDS: \[(.*?)\]", extension, re.S)
        self.assertIsNotNone(web_block)
        self.assertIsNotNone(extension_block)
        self.assertEqual(set(re.findall(r'"([a-z_]+)"', web_block.group(1))), expected)
        self.assertEqual(set(re.findall(r'"([a-z_]+)"', extension_block.group(1))), expected)

    def test_web_and_extension_messages_do_not_drift(self) -> None:
        """메시지 이름이 한쪽만 바뀌면 조용히 끊긴다 — Quiz Bank 의 둘이 붙은 날(2026-10-04) 세웠다."""
        web = (ROOT / "web" / "src" / "bridge" / "protocol.ts").read_text(encoding="utf-8")
        extension = (EXTENSION / "protocol.js").read_text(encoding="utf-8")
        web_block = re.search(r"export const MESSAGES = \{(.*?)\} as const", web, re.S)
        extension_block = re.search(r"MESSAGES: \{(.*?)\n  \},", extension, re.S)
        pairs = lambda block: dict(re.findall(r'(\w+): "([A-Z_]+)"', block.group(1)))  # noqa: E731
        self.assertEqual(pairs(web_block), pairs(extension_block))
        self.assertEqual(pairs(web_block)["bankReady"], "STUDYEZ_BANK_READY")

    def test_bank_answer_only_from_a_bank_tab(self) -> None:
        """답 본문은 bank 로 연 ChatGPT 탭에서, 완료 표시가 있을 때만 받는다. 그 탭의 링크는 예습에 안 붙는다."""
        source = (EXTENSION / "background.js").read_text(encoding="utf-8")
        handler = source[source.index('"STUDYEZ_BANK_ANSWER"'):]
        self.assertIn('providerForSender(sender) !== "chatgpt"', handler[:400])
        self.assertIn("raw.includes(BANK_MARK)", handler[:600])
        self.assertIn('watch.mode !== "bank"', handler[:1200])
        self.assertIn('watch.mode === "bank" ? (share ? "chatgpt_bank_share" : "chatgpt_bank")', source)

    def test_background_knows_each_conversation_shape(self) -> None:
        source = (EXTENSION / "background.js").read_text(encoding="utf-8")
        for marker in ("app\\/", "chat\\/", "c\\/"):
            self.assertIn(marker, source)
        for provider in ("chatgpt", "gemini", "claude"):
            self.assertIn(f'{provider}: {{ origin:', source)

    def test_server_accepts_each_providers_own_links_only(self) -> None:
        conversations = {
            "chatgpt": "https://chatgpt.com/c/abc-123",
            "gemini": "https://gemini.google.com/app/abc_123",
            "claude": "https://claude.ai/chat/12345678-abcd-4321-9999-abcdefabcdef",
        }
        shares = {
            "chatgpt": "https://chatgpt.com/share/abc-123",
            "gemini": "https://g.co/gemini/share/abc_123",
            "claude": "https://claude.ai/share/12345678-abcd-4321-9999-abcdefabcdef",
        }
        for provider, url in conversations.items():
            self.assertTrue(conversation_url(url, provider))
            self.assertFalse(conversation_url(url, "claude" if provider != "claude" else "gemini"))
        for provider, url in shares.items():
            self.assertTrue(share_url(url, provider))
            self.assertFalse(share_url(url, "claude" if provider != "claude" else "gemini"))


if __name__ == "__main__":
    unittest.main()

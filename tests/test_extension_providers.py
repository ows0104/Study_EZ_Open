from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "chrome-extension"
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
            "chatgpt", "chatgpt_share", "gemini", "gemini_share", "claude", "claude_share"
        }
        web_block = re.search(r"export const LINK_KINDS = \[(.*?)\] as const", web, re.S)
        extension_block = re.search(r"LINK_KINDS: \[(.*?)\]", extension, re.S)
        self.assertIsNotNone(web_block)
        self.assertIsNotNone(extension_block)
        self.assertEqual(set(re.findall(r'"([a-z_]+)"', web_block.group(1))), expected)
        self.assertEqual(set(re.findall(r'"([a-z_]+)"', extension_block.group(1))), expected)

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

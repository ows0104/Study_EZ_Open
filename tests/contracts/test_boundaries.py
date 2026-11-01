"""Producer/consumer compatibility and packaging boundaries."""
import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_modules_are_the_same_implementation_including_private_helpers():
    for path in (ROOT / 'studyez_contracts/bank').glob('*.py'):
        if path.stem == '__init__':
            continue
        canonical = importlib.import_module(f'studyez_contracts.bank.{path.stem}')
        legacy = importlib.import_module(f'server.app.bank_validation.{path.stem}')
        assert legacy is canonical


def test_contracts_do_not_import_application_or_third_party_runtime():
    stdlib = sys.stdlib_module_names
    for path in (ROOT / 'studyez_contracts/bank').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                assert all(alias.name.split('.')[0] in stdlib for alias in node.names), path
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert node.module.split('.')[0] in stdlib, path


def test_generation_and_bank_adapter_have_no_server_imports():
    # runner.feedback is an existing read-only operations/DB adapter, not generation.
    for paths in ((ROOT / 'quizbank').rglob('*.py'), [ROOT / 'runner/bank.py']):
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or '').startswith(('server.', 'app.')), path


def test_packaged_prompt_matches_canonical_text_and_hashes():
    import hashlib
    subprocess.run(['node', 'web/scripts/prepare-prompts.mjs'], cwd=ROOT, check=True)
    bundle = json.loads((ROOT / 'web/public/bank-prompt.json').read_text(encoding='utf-8'))
    canonical = ROOT / 'content/prompts/bank'
    for name, expected in bundle['sourceSha256'].items():
        assert hashlib.sha256((canonical / name).read_bytes()).hexdigest() == expected
    assert bundle['template'] == (canonical / 'bankPrompt.md').read_bytes().decode('utf-8')
    assert bundle['deliveries']['file'] == (canonical / 'fileDelivery.md').read_bytes().decode('utf-8')

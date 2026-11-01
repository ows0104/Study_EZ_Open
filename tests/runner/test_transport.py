"""Public HTTP/file contracts and partial-upload failures, without a real server."""
import io
import json
import unicodedata
import urllib.error
from pathlib import Path

import pytest

from runner import publish, transport
from runner.bank_flow import execution, upload


def test_api_auth_and_signed_file_headers_stay_separate(tmp_path, monkeypatch):
    sent = []

    def open_request(request, timeout):
        body = request.data.read() if hasattr(request.data, 'read') else request.data
        sent.append((request, timeout, body))
        return io.BytesIO(b'{"ok":true}')

    monkeypatch.setattr(transport.urllib.request, 'urlopen', open_request)
    client = publish.Client('https://api.example.test/', 'test-only-token', timeout=27)
    assert client.call('PUT', '/api/example', {'title': '강의'}) == {'ok': True}
    request, timeout, body = sent[0]
    assert request.full_url == 'https://api.example.test/api/example'
    assert request.get_method() == 'PUT' and timeout == 27
    assert request.get_header('Authorization') == 'Bearer test-only-token'
    assert request.get_header('Content-type') == 'application/json'
    assert json.loads(body) == {'title': '강의'}

    file = tmp_path / 'evidence.md'
    file.write_bytes('원본\r\n'.encode('utf-8'))
    for target, expected in (
        ('https://storage.example.test/object?sig=test-only', 'https://storage.example.test/object?sig=test-only'),
        ('/api/local-storage/object', 'https://api.example.test/api/local-storage/object'),
    ):
        client.put_file(target, file)
        request, timeout, body = sent[-1]
        assert request.full_url == expected and request.get_method() == 'PUT'
        assert request.get_header('Authorization') is None
        assert request.get_header('Content-type') == 'text/markdown'
        assert request.get_header('Content-length') == str(len(body))
        assert body == file.read_bytes() and timeout == 27
    assert publish.Client is transport.Client
    assert publish.Upload is transport.Upload
    assert publish.PublishError is transport.PublishError


def test_http_error_keeps_shared_exception_and_omits_signed_query(monkeypatch):
    def reject(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 409, 'stale', {}, io.BytesIO(b'changed'))

    monkeypatch.setattr(transport.urllib.request, 'urlopen', reject)
    with pytest.raises(publish.PublishError) as caught:
        transport.Client('https://api.example.test', 'test-only').call('PUT', '/bank?sig=private')
    assert str(caught.value) == '409 PUT https://api.example.test/bank — changed'


@pytest.mark.parametrize('failures,attempts,pauses', [(0, 1, []), (1, 2, [2]), (3, 3, [2, 4])])
def test_upload_retry_budget_and_backoff_are_unchanged(tmp_path, monkeypatch, failures, attempts, pauses):
    calls, sleeps = [], []

    class Client:
        def put_file(self, url, path):
            calls.append((url, path))
            if len(calls) <= failures:
                raise publish.PublishError('interrupted')

    monkeypatch.setattr(transport.time, 'sleep', sleeps.append)
    artifact = publish.Upload('bank_media', tmp_path / 'page.png')
    if failures == 3:
        with pytest.raises(publish.PublishError):
            publish._put_with_retry(Client(), '/signed', artifact)
    else:
        publish._put_with_retry(Client(), '/signed', artifact)
    assert calls == [('/signed', artifact.path)] * attempts
    assert sleeps == pauses


def test_upload_manifest_and_lecture_path_keep_nfc_and_escaping(tmp_path):
    name = unicodedata.normalize('NFD', '근거.md')
    path = tmp_path / name
    path.write_bytes(b'1234')
    assert transport.Upload('jokbo', path).payload() == {
        'kind': 'jokbo', 'filename': '근거.md', 'sizeBytes': 4, 'contentType': 'text/markdown'}
    assert transport.lecture_path('a/b', 'r x', '/bank') == '/api/admin/lectures/a%2Fb/r%20x/bank'


def test_missing_image_confirmation_prevents_bank_publication(tmp_path):
    slides = tmp_path / 'slides'
    slides.mkdir()
    (slides / 'page.png').write_bytes(b'png')
    calls = []

    class Client:
        def call(self, method, path, payload):
            calls.append((method, path))
            if path.endswith('/uploads'):
                return {'files': [{'filename': 'page.png', 'uploadUrl': '/signed'}]}
            if path.endswith('/uploads/complete'):
                return {'missing': ['page.png']}
            raise AssertionError('The bank must not be published after an incomplete image upload')

        def put_file(self, url, path):
            assert path.read_bytes() == b'png'
            calls.append(('FILE', url))

    with pytest.raises(publish.PublishError, match='page.png'):
        upload.publish_result(Client(), 'subject', 'demo', {'respondedAt': 'unchanged'}, tmp_path, {})
    assert [method for method, _ in calls] == ['POST', 'POST', 'FILE', 'POST']
    assert not (tmp_path / 'upload-timings.json').exists()


def test_failed_maintenance_report_never_replaces_bank(capsys):
    sent = []

    class Client:
        def call(self, method, path, payload):
            sent.append((method, path, payload))
            raise publish.PublishError('offline')

    result = upload.report_failure(Client(), '/lecture',
        {'respondedAt': 'original-time', 'existingBank': {}, 'baseBuildId': 'original-build'},
        'failed', revision={'audit': 'preserved'})
    assert result == 1
    assert sent == [('PUT', '/lecture/bank', {
        'respondedAt': 'original-time', 'message': 'failed',
        'revision': {'audit': 'preserved'}, 'baseBuildId': 'original-build'})]
    assert '실패를 서버에 적지 못했다' in capsys.readouterr().out


def test_missing_response_revision_stops_before_files_or_generator(tmp_path, monkeypatch):
    class Client:
        def call(self, method, path):
            assert method == 'GET'
            return {'title': 'incomplete response', 'raw': 'STUDYEZ_BANK_COMPLETE'}

    def unexpected(*args, **kwargs):
        raise AssertionError('Incomplete metadata must not start processing')

    monkeypatch.setattr(execution, 'run_forwarded', unexpected)
    with pytest.raises(KeyError, match='respondedAt'):
        execution.run(Client(), tmp_path, 'subject', 'demo', '2026', '2025', tmp_path)
    assert list(tmp_path.iterdir()) == []

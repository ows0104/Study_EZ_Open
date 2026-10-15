from runner import publish


class FakeClient:
    def __init__(self, remote):
        self.remote = remote
        self.writes = []

    def call(self, method, path, payload=None):
        if method == "GET" and path == "/api/admin/previews":
            return {"previews": self.remote}
        if path.endswith("/uploads"):
            return {"files": []}
        if path.endswith("/uploads/complete"):
            return {"missing": []}
        self.writes.append((method, path, payload))
        return {}


def send_plan(remote):
    plan = publish.LecturePlan(subject="약리학", run_id="261013_01", item=None)
    plan.preview_url = "https://chatgpt.com/share/old"
    client = FakeClient(remote)
    report = publish.Report()
    publish._publish_one(plan, client, {}, report, force=False, log=lambda _: None)
    return client, report


def test_sweep_does_not_restore_link_replaced_after_planning():
    client, report = send_plan([{"subject": "약리학", "runId": "261013_01",
                                 "shareUrl": "https://chatgpt.com/share/new"}])
    assert not client.writes
    assert report.previews == 0


def test_existing_matching_link_needs_no_write_back():
    client, report = send_plan([{"subject": "약리학", "runId": "261013_01",
                                 "shareUrl": "https://chatgpt.com/share/old"}])
    assert not client.writes
    assert report.previews == 0


def test_local_link_can_bootstrap_missing_server_link():
    client, report = send_plan([])
    assert client.writes[0][2]["shareUrl"] == "https://chatgpt.com/share/old"
    assert report.previews == 1

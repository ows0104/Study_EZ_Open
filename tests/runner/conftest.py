import pytest


@pytest.fixture(autouse=True)
def no_choices_model(request, monkeypatch):
    """게시 뒤 선지 작성은 test_root_choices_publish.py가 따로 본다. 다른 러너 검사는 모델·하위 프로세스를 부르지 않는다."""
    if request.module.__name__.endswith("test_root_choices_publish"):
        return
    from runner import root_choices
    monkeypatch.setattr(root_choices, "build", lambda *a, **k: None)

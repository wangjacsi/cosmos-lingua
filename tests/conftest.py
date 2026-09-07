"""실제 사용자 저장소·기억을 사용하지 않는 원본 에이전트 검사."""
import os
import tempfile

os.environ["COSMOS_HOME"] = tempfile.mkdtemp(prefix="lingua-tests-")
os.environ["COSMOS_LANG"] = "en"

import pytest


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    from cosmos.core import store
    from lingua_live import LinguaLive
    store._reset_for_tests()
    monkeypatch.setattr(store.provider(), "db_path", lambda: tmp_path / "store.db")
    LinguaLive._busy.clear()
    LinguaLive._pending.clear()
    yield
    store._reset_for_tests()

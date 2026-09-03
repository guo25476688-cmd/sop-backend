"""
pytest 夹具：为每个测试用独立的临时 SQLite 库启动 app。
必须在导入 main 之前设置好环境变量。
"""

import importlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def app_module(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("SOP_DB_PATH", tmp.name)
    monkeypatch.setenv("ADMIN_TOKEN", "")
    monkeypatch.setenv("APP_SECRET_KEY", "")
    monkeypatch.setenv("DIFY_BASE_URL", "")
    for aid in ("A1", "A2", "A3", "A4", "R1", "R2"):
        monkeypatch.delenv(f"DIFY_KEY_{aid}", raising=False)

    import config
    import database
    import main
    importlib.reload(config)
    importlib.reload(database)
    importlib.reload(main)
    main.app.config.update(TESTING=True)

    yield main

    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(tmp.name + suffix)
        except OSError:
            pass


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()

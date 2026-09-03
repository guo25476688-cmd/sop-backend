import base64
import json


def _basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


# ──────────────────────────── 基础 ────────────────────────────

def test_healthz(client):
    assert client.get("/healthz").get_json() == {"ok": True}


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"AI" in r.data


# ──────────────────────────── 配置 ────────────────────────────

def test_config_get_hides_raw_by_default(client):
    data = client.get("/api/config").get_json()
    assert set(data["keys"]) == {"A1", "A2", "A3", "A4", "R1", "R2"}
    for entry in data["keys"].values():
        assert "raw" not in entry
        assert entry["configured"] is False


def test_config_roundtrip_with_reveal(client):
    put = client.put("/api/config", json={"base_url": "https://dify.example/v1",
                                          "key_a1": "app-secret-key-123456"})
    assert put.status_code == 200
    data = client.get("/api/config?reveal=1").get_json()
    assert data["base_url"] == "https://dify.example/v1"
    assert data["keys"]["A1"]["raw"] == "app-secret-key-123456"
    assert data["keys"]["A1"]["masked"].startswith("app-secr")
    assert data["keys"]["A1"]["configured"] is True


def test_config_masked_value_not_overwriting(client):
    client.put("/api/config", json={"key_a1": "app-secret-key-123456"})
    masked = client.get("/api/config").get_json()["keys"]["A1"]["masked"]
    # 前端回填掩码串重新保存 —— 不应把真实 key 覆盖成掩码
    client.put("/api/config", json={"key_a1": masked})
    assert client.get("/api/config?reveal=1").get_json()["keys"]["A1"]["raw"] == "app-secret-key-123456"


def test_config_encrypts_at_rest(client, app_module, monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(app_module.Config, "APP_SECRET_KEY", key)
    # database 模块引用的是同一个 Config 类，改一次即可；这里显式确认
    import database
    assert database.Config is app_module.Config

    client.put("/api/config", json={"key_a1": "app-plaintext-xyz"})
    conn = app_module._new_connection()
    stored = conn.execute("SELECT key_a1 FROM config WHERE id=1").fetchone()[0]
    conn.close()
    assert stored.startswith("enc:v1:")
    assert "app-plaintext-xyz" not in stored
    # 读回仍是明文
    assert client.get("/api/config?reveal=1").get_json()["keys"]["A1"]["raw"] == "app-plaintext-xyz"


# ──────────────────────────── 项目 CRUD ────────────────────────────

def test_project_crud(client):
    cid = client.post("/api/projects", json={"name": "测试活动", "activity_type": "培训"}).get_json()["id"]

    lst = client.get("/api/projects").get_json()
    assert lst["total"] == 1 and lst["items"][0]["id"] == cid

    client.put(f"/api/projects/{cid}", json={"a1_data": {"outline": ["阶段一"]}, "status": "active"})
    got = client.get(f"/api/projects/{cid}").get_json()
    assert got["a1_data"] == {"outline": ["阶段一"]}
    assert got["status"] == "active"

    assert client.delete(f"/api/projects/{cid}").status_code == 200
    assert client.get(f"/api/projects/{cid}").status_code == 404


def test_project_requires_name(client):
    assert client.post("/api/projects", json={"activity_type": "培训"}).status_code == 400


def test_project_update_ignores_unknown_columns(client):
    cid = client.post("/api/projects", json={"name": "x"}).get_json()["id"]
    # 恶意/未知列名不应进入 SQL
    r = client.put(f"/api/projects/{cid}", json={"name = 'h'--": 1, "id": 999})
    assert r.status_code == 200
    assert client.get(f"/api/projects/{cid}").get_json()["id"] == cid


def test_project_list_bad_pagination(client):
    assert client.get("/api/projects?page=abc&page_size=-5").status_code == 200


# ──────────────────────────── Dify 代理 ────────────────────────────

def test_dify_proxy_without_config(client):
    r = client.post("/api/dify/workflow/A1", json={"inputs": {}})
    assert r.status_code == 400


def test_dify_proxy_bad_app_id(client):
    assert client.post("/api/dify/workflow/ZZ", json={"inputs": {}}).status_code == 400


# ──────────────────────────── 导出脱敏 ────────────────────────────

def test_export_masks_secrets_by_default(client):
    client.put("/api/config", json={"key_a1": "app-secret-key-123456"})
    plain = client.get("/api/export").get_json()
    assert plain["secrets_included"] is False
    assert "****" in plain["config"]["keys"]["A1"]
    revealed = client.get("/api/export?include_secrets=1").get_json()
    assert revealed["config"]["keys"]["A1"] == "app-secret-key-123456"


# ──────────────────────────── 鉴权 ────────────────────────────

def test_admin_gate(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module.Config, "ADMIN_TOKEN", "s3cret")

    assert client.get("/admin").status_code == 401
    assert client.put("/api/config", json={"base_url": "x"}).status_code == 401
    assert client.delete("/api/projects/1").status_code == 401

    ok = client.get("/admin", headers=_basic("admin", "s3cret"))
    assert ok.status_code in (200, 404)  # 200 有页面 / 404 页面缺失，均视为通过鉴权
    # 读接口不受影响
    assert client.get("/api/projects").status_code == 200


def test_error_handler_returns_json(client):
    r = client.get("/api/projects/not-an-int")
    assert r.status_code == 404
    assert r.is_json

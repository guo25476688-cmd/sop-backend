"""
企业级 AI 应用运营平台 —— 后端服务（活动运营场景）
Flask + SQLite，提供项目管理、API 配置、Dify 代理、统计日志等接口。
AI 编排全部在 Dify 侧实现，本服务只做鉴权转发与调用留痕。
启动方式: python main.py
"""

import hmac
import json
import logging
import time
import os
from datetime import datetime
from functools import wraps

import httpx
from flask import (Flask, request, jsonify, send_file, Response, g,
                   has_app_context, stream_with_context)
from werkzeug.exceptions import HTTPException

import demo_fixtures
from config import Config
from database import (get_db as _new_connection, init_db, add_log, add_dify_call,
                      encrypt_secret, decrypt_secret)

# ──────────────────────────── App 初始化 ────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.json.ensure_ascii = False  # 错误信息里的中文不转义，便于前端展示

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

APP_KEY_MAP = {
    "A1": "key_a1", "A2": "key_a2", "A3": "key_a3",
    "A4": "key_a4", "R1": "key_r1", "R2": "key_r2"
}

if not Config.ADMIN_TOKEN:
    app.logger.warning("未设置 ADMIN_TOKEN —— 管理面与写接口处于开放的开发模式")
if not Config.APP_SECRET_KEY:
    app.logger.warning("未设置 APP_SECRET_KEY —— Dify API Key 将以明文存储于数据库")


# ──────────────────────────── 数据库连接管理 ────────────────────────────

def get_db():
    """
    返回一个数据库连接。在请求 / 应用上下文内会登记，请求结束时由 teardown
    统一关闭，避免异常路径下的连接泄漏；上下文外（脚本 / 测试）返回独立连接。
    """
    conn = _new_connection()
    if has_app_context():
        g.setdefault("_db_conns", []).append(conn)
    return conn


@app.teardown_appcontext
def _close_db_connections(exc):
    for conn in g.pop("_db_conns", []):
        try:
            conn.close()
        except Exception:  # pragma: no cover - 关闭失败无需影响响应
            pass


# ──────────────────────────── 鉴权 ────────────────────────────

def _is_admin() -> bool:
    """开发模式（未配置 ADMIN_TOKEN）恒为 True；否则校验 HTTP Basic 密码。"""
    if not Config.ADMIN_TOKEN:
        return True
    auth = request.authorization
    if auth and auth.password:
        return hmac.compare_digest(auth.password, Config.ADMIN_TOKEN)
    token = request.headers.get("X-Admin-Token", "")
    return bool(token) and hmac.compare_digest(token, Config.ADMIN_TOKEN)


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _is_admin():
            resp = jsonify({"error": "需要管理员认证"})
            resp.status_code = 401
            resp.headers["WWW-Authenticate"] = 'Basic realm="admin"'
            return resp
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def _auth_warning_header(resp):
    if not Config.ADMIN_TOKEN:
        resp.headers["X-Auth-Warning"] = "dev-mode: no ADMIN_TOKEN configured"
    return resp


# ──────────────────────────── 错误处理 ────────────────────────────

@app.errorhandler(HTTPException)
def _handle_http_exc(e):
    return jsonify({"error": e.description, "status": e.code}), e.code


@app.errorhandler(Exception)
def _handle_uncaught(e):
    app.logger.exception("未捕获异常: %s", e)
    return jsonify({"error": "服务器内部错误"}), 500


# ──────────────────────────── Dify 连接解析 ────────────────────────────

def resolve_dify(app_id):
    """
    合并环境变量与 config 表，返回 (base_url, key, key_source)。
    环境变量优先（作为权威来源）。key_source ∈ {"env", "db", ""}。
    """
    db = get_db()
    cfg = get_config_dict(db)
    base_url = (Config.DIFY_BASE_URL or cfg.get("base_url", "")).rstrip("/")
    env_key = Config.dify_key_from_env(app_id)
    if env_key:
        return base_url, env_key, "env"
    db_key = decrypt_secret(cfg.get(APP_KEY_MAP[app_id], ""))
    return base_url, db_key, ("db" if db_key else "")


def mask_key(key: str) -> str:
    if not key:
        return ""
    return (key[:8] + "****" + key[-4:]) if len(key) > 12 else "****"


def _demo_log(call_type, app_id, snapshot, project_id):
    try:
        add_dify_call(get_db(), app_id, call_type, snapshot, "[demo]", 0,
                      "success", "", project_id)
    except Exception:  # pragma: no cover
        pass


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def parse_json_field(val):
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val) if val else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def project_row_to_response(row):
    d = row_to_dict(row)
    if d is None:
        return None
    for k in ("a1_data", "a2_data", "a3_data", "a4_data", "r1_data", "r2_data", "versions", "feed"):
        d[k] = parse_json_field(d.get(k))
    return d


def get_config_dict(db):
    row = db.execute("SELECT * FROM config WHERE id = 1").fetchone()
    return row_to_dict(row) if row else {}


# ══════════════════════════════════════════════════════════════════
#  前端页面
# ══════════════════════════════════════════════════════════════════

@app.route("/")
def serve_frontend():
    html_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({"message": "前端页面未部署。请将 HTML 文件放入 static/ 目录。"})


@app.route("/admin")
@require_admin
def serve_admin():
    html_path = os.path.join(FRONTEND_DIR, "admin.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({"message": "后台管理页面未部署。请将 admin.html 放入 static/ 目录。"})


# ══════════════════════════════════════════════════════════════════
#  1. API 配置管理
# ══════════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def get_config():
    db = get_db()
    cfg = get_config_dict(db)
    base_url = Config.DIFY_BASE_URL or cfg.get("base_url", "")
    reveal = _is_admin() and request.args.get("reveal") == "1"
    result = {
        "base_url": base_url,
        "base_url_source": "env" if Config.DIFY_BASE_URL else "db",
        "demo_mode": Config.DEMO_MODE,
        "keys": {},
    }
    for app_id, col in APP_KEY_MAP.items():
        env_key = Config.dify_key_from_env(app_id)
        key = env_key or decrypt_secret(cfg.get(col, ""))
        source = "env" if env_key else ("db" if key else "")
        entry = {
            "configured": bool(key),
            "masked": mask_key(key),
            "source": source,
            "editable": source != "env",
        }
        if reveal:
            entry["raw"] = key
        result["keys"][app_id] = entry
    result["updated_at"] = cfg.get("updated_at", "")
    return jsonify(result)


@app.route("/api/config", methods=["PUT"])
@require_admin
def update_config():
    data = request.get_json(force=True, silent=True) or {}
    now = datetime.now().isoformat()
    db = get_db()
    cfg = get_config_dict(db)

    base_url = Config.DIFY_BASE_URL or data.get("base_url", "")
    new_keys = {}
    skipped = []
    for app_id, col in APP_KEY_MAP.items():
        if Config.dify_key_from_env(app_id):
            new_keys[col] = cfg.get(col, "")   # 环境变量托管，忽略 UI 提交
            skipped.append(app_id)
            continue
        incoming = (data.get(col) or "").strip()
        # 前端回传掩码串时视为"未修改"，保留原值
        if incoming and incoming == mask_key(decrypt_secret(cfg.get(col, ""))):
            new_keys[col] = cfg.get(col, "")
        else:
            new_keys[col] = encrypt_secret(incoming)

    db.execute(
        """UPDATE config SET
           base_url=?, key_a1=?, key_a2=?, key_a3=?, key_a4=?, key_r1=?, key_r2=?, updated_at=?
           WHERE id=1""",
        (base_url, new_keys["key_a1"], new_keys["key_a2"], new_keys["key_a3"],
         new_keys["key_a4"], new_keys["key_r1"], new_keys["key_r2"], now)
    )
    db.commit()
    add_log(db, "update_config", "config", f"更新 API 配置，平台地址: {base_url}")
    return jsonify({"ok": True, "updated_at": now, "env_managed": skipped})


def _probe_dify(base_url, key, timeout=15):
    resp = httpx.get(f"{base_url}/parameters",
                     headers={"Authorization": f"Bearer {key}"},
                     timeout=timeout, verify=Config.DIFY_VERIFY_SSL)
    return resp


@app.route("/api/config/test/<app_id>", methods=["POST"])
@require_admin
def test_connection(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"ok": False, "error": f"无效的应用编号: {app_id}"}), 400

    base_url, key, _ = resolve_dify(app_id)
    if not base_url:
        return jsonify({"ok": False, "error": "未配置 Dify 平台地址"})
    if not key:
        return jsonify({"ok": False, "error": f"{app_id} 未配置 API Key"})

    try:
        resp = _probe_dify(base_url, key)
        if resp.status_code == 200:
            return jsonify({"ok": True, "app_id": app_id, "status": "connected"})
        return jsonify({"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
    except httpx.ConnectError as e:
        return jsonify({"ok": False, "error": f"连接失败，请检查 Dify 地址是否正确、后端能否访问该地址: {e}"})
    except httpx.TimeoutException:
        return jsonify({"ok": False, "error": "连接超时（15秒），请检查网络或 Dify 平台是否可达"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/config/test-all", methods=["POST"])
@require_admin
def test_all_connections():
    results = {}
    for app_id in APP_KEY_MAP:
        base_url, key, _ = resolve_dify(app_id)
        if not base_url or not key:
            results[app_id] = {"ok": False, "error": "未配置"}
            continue
        try:
            resp = _probe_dify(base_url, key)
            results[app_id] = {"ok": resp.status_code == 200, "status": resp.status_code}
        except Exception as e:
            results[app_id] = {"ok": False, "error": str(e)}
    return jsonify(results)


# ══════════════════════════════════════════════════════════════════
#  2. 项目 CRUD
# ══════════════════════════════════════════════════════════════════

# 允许经 PUT /api/projects/<id> 更新的列（白名单，防止列名注入）
PROJECT_UPDATABLE = {
    "name", "activity_type", "department", "date", "target", "budget",
    "background", "status",
    "a1_data", "a2_data", "a3_data", "a4_data", "r1_data", "r2_data",
    "versions", "feed",
}


def _int_arg(name, default, lo=None, hi=None):
    try:
        v = int(request.args.get(name, default))
    except (TypeError, ValueError):
        v = default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


@app.route("/api/projects", methods=["GET"])
def list_projects():
    status = request.args.get("status")
    search = request.args.get("search")
    page = _int_arg("page", 1, lo=1)
    page_size = _int_arg("page_size", 20, lo=1, hi=200)

    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if search:
        conditions.append("(name LIKE ? OR department LIKE ? OR activity_type LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    db = get_db()

    total = db.execute(f"SELECT COUNT(*) FROM projects {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM projects {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    db.close()

    return jsonify({
        "items": [project_row_to_response(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    })


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json(force=True, silent=True) or {}
    if not (data.get("name") or "").strip():
        return jsonify({"error": "项目名称不能为空"}), 400
    now = datetime.now().isoformat()
    db = get_db()
    cursor = db.execute(
        """INSERT INTO projects
           (name, activity_type, department, date, target, budget, background, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)""",
        (data.get("name", ""), data.get("activity_type", ""), data.get("department", ""),
         data.get("date", ""), data.get("target", ""), data.get("budget", ""),
         data.get("background", ""), now, now)
    )
    db.commit()
    pid = cursor.lastrowid
    add_log(db, "create_project", "project", f"创建项目: {data.get('name', '')}", pid)
    db.close()
    return jsonify({"ok": True, "id": pid})


@app.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project(project_id):
    db = get_db()
    row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "项目不存在"}), 404
    return jsonify(project_row_to_response(row))


@app.route("/api/projects/<int:project_id>", methods=["PUT"])
def update_project(project_id):
    db = get_db()
    if not db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone():
        db.close()
        return jsonify({"error": "项目不存在"}), 404

    data = request.get_json(force=True, silent=True) or {}
    updates, params = [], []

    for key, value in data.items():
        if key not in PROJECT_UPDATABLE:
            continue
        if key.endswith("_data") or key in ("versions", "feed"):
            params.append(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)
        else:
            params.append(value)
        updates.append(f"{key} = ?")

    if not updates:
        return jsonify({"ok": True, "message": "无变更"})

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(project_id)

    db.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    add_log(db, "update_project", "project", f"更新字段: {', '.join(data.keys())}", project_id)
    db.close()
    return jsonify({"ok": True})


@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@require_admin
def delete_project(project_id):
    db = get_db()
    row = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        return jsonify({"error": "项目不存在"}), 404
    name = row[0]
    # 先记日志（此时项目还在，外键成立），再删除；日志的 project_id 会随之置空
    add_log(db, "delete_project", "project", f"删除项目: {name}（#{project_id}）", project_id)
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════
#  3. Dify 代理
# ══════════════════════════════════════════════════════════════════

def _valid_app_id(app_id):
    return app_id.upper() in APP_KEY_MAP


@app.route("/api/dify/workflow/<app_id>", methods=["POST"])
@require_admin
def proxy_workflow(app_id):
    app_id = app_id.upper()
    if not _valid_app_id(app_id):
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    base_url, key, _ = resolve_dify(app_id)
    data = request.get_json(force=True, silent=True) or {}
    inputs_snapshot = json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000]

    if not key and Config.DEMO_MODE:
        _demo_log("workflow", app_id, inputs_snapshot, data.get("project_id"))
        return jsonify(demo_fixtures.workflow_result(app_id))
    if not base_url or not key:
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    db = get_db()
    t0 = time.time()
    try:
        with httpx.Client(timeout=Config.DIFY_TIMEOUT, verify=Config.DIFY_VERIFY_SSL) as client:
            resp = client.post(
                f"{base_url}/workflows/run",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"inputs": data.get("inputs", {}), "response_mode": "blocking",
                      "user": data.get("user", "sop-platform")}
            )
            duration = int((time.time() - t0) * 1000)
            result = resp.json()
            add_dify_call(db, app_id, "workflow", inputs_snapshot,
                          json.dumps(result, ensure_ascii=False)[:5000],
                          duration, "success", "", data.get("project_id"))
            return jsonify(result)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        app.logger.warning("Dify workflow 调用失败 app=%s: %s", app_id, e)
        add_dify_call(db, app_id, "workflow", inputs_snapshot,
                      "", duration, "error", str(e), data.get("project_id"))
        return jsonify({"error": f"Dify 调用失败: {str(e)}"}), 502


@app.route("/api/dify/workflow-stream/<app_id>", methods=["POST"])
@require_admin
def proxy_workflow_stream(app_id):
    app_id = app_id.upper()
    if not _valid_app_id(app_id):
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    base_url, key, _ = resolve_dify(app_id)
    data = request.get_json(force=True, silent=True) or {}
    inputs_snapshot = json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000]
    project_id = data.get("project_id")
    demo = (not key) and Config.DEMO_MODE

    if not demo and (not base_url or not key):
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    def _record(status, output, err, duration):
        conn = _new_connection()
        try:
            add_dify_call(conn, app_id, "workflow_stream", inputs_snapshot,
                          output, duration, status, err, project_id)
        finally:
            conn.close()

    def generate():
        t0 = time.time()
        if demo:
            for line in demo_fixtures.workflow_sse(app_id):
                yield f"data: {line}\n\n"
            _record("success", "[demo]", "", int((time.time() - t0) * 1000))
            return
        try:
            with httpx.Client(timeout=Config.DIFY_TIMEOUT, verify=Config.DIFY_VERIFY_SSL) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/workflows/run",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"inputs": data.get("inputs", {}), "response_mode": "streaming",
                          "user": data.get("user", "sop-platform")}
                ) as resp:
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            yield f"{line}\n\n"
            _record("success", "[stream]", "", int((time.time() - t0) * 1000))
        except Exception as e:
            app.logger.warning("Dify workflow-stream 调用失败 app=%s: %s", app_id, e)
            _record("error", "", str(e), int((time.time() - t0) * 1000))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/dify/chat/<app_id>", methods=["POST"])
@require_admin
def proxy_chat(app_id):
    app_id = app_id.upper()
    if not _valid_app_id(app_id):
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    base_url, key, _ = resolve_dify(app_id)
    data = request.get_json(force=True, silent=True) or {}
    query_snapshot = json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000]

    if not key and Config.DEMO_MODE:
        _demo_log("chat", app_id, query_snapshot, data.get("project_id"))
        return jsonify(demo_fixtures.chat_result())
    if not base_url or not key:
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    body = {
        "query": data.get("query", ""),
        "inputs": data.get("inputs", {}),
        "response_mode": "blocking",
        "user": data.get("user", "sop-platform")
    }
    if data.get("conversation_id"):
        body["conversation_id"] = data["conversation_id"]

    db = get_db()
    t0 = time.time()
    try:
        with httpx.Client(timeout=Config.DIFY_TIMEOUT, verify=Config.DIFY_VERIFY_SSL) as client:
            resp = client.post(
                f"{base_url}/chat-messages",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body
            )
            duration = int((time.time() - t0) * 1000)
            result = resp.json()
            add_dify_call(db, app_id, "chat", query_snapshot,
                          json.dumps(result, ensure_ascii=False)[:5000],
                          duration, "success", "", data.get("project_id"))
            return jsonify(result)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        app.logger.warning("Dify chat 调用失败 app=%s: %s", app_id, e)
        add_dify_call(db, app_id, "chat", query_snapshot,
                      "", duration, "error", str(e), data.get("project_id"))
        return jsonify({"error": f"Dify 调用失败: {str(e)}"}), 502


@app.route("/api/dify/chat-stream/<app_id>", methods=["POST"])
@require_admin
def proxy_chat_stream(app_id):
    app_id = app_id.upper()
    if not _valid_app_id(app_id):
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    base_url, key, _ = resolve_dify(app_id)
    data = request.get_json(force=True, silent=True) or {}
    query_snapshot = json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000]
    project_id = data.get("project_id")
    demo = (not key) and Config.DEMO_MODE

    if not demo and (not base_url or not key):
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    body = {
        "query": data.get("query", ""),
        "inputs": data.get("inputs", {}),
        "response_mode": "streaming",
        "user": data.get("user", "sop-platform")
    }
    if data.get("conversation_id"):
        body["conversation_id"] = data["conversation_id"]

    def _record(status, output, err, duration):
        conn = _new_connection()
        try:
            add_dify_call(conn, app_id, "chat_stream", query_snapshot,
                          output, duration, status, err, project_id)
        finally:
            conn.close()

    def generate():
        t0 = time.time()
        if demo:
            for line in demo_fixtures.chat_sse():
                yield f"data: {line}\n\n"
            _record("success", "[demo]", "", int((time.time() - t0) * 1000))
            return
        try:
            with httpx.Client(timeout=Config.DIFY_TIMEOUT, verify=Config.DIFY_VERIFY_SSL) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/chat-messages",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=body
                ) as resp:
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            yield f"{line}\n\n"
            _record("success", "[stream]", "", int((time.time() - t0) * 1000))
        except Exception as e:
            app.logger.warning("Dify chat-stream 调用失败 app=%s: %s", app_id, e)
            _record("error", "", str(e), int((time.time() - t0) * 1000))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ══════════════════════════════════════════════════════════════════
#  4. 统计与日志
# ══════════════════════════════════════════════════════════════════

@app.route("/api/stats", methods=["GET"])
def get_stats():
    db = get_db()
    stats = {}

    stats["total_projects"] = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    stats["projects_by_status"] = {
        r[0]: r[1] for r in db.execute("SELECT status, COUNT(*) FROM projects GROUP BY status").fetchall()
    }
    stats["total_dify_calls"] = db.execute("SELECT COUNT(*) FROM dify_calls").fetchone()[0]
    stats["calls_by_app"] = {
        r[0]: r[1] for r in db.execute("SELECT app_id, COUNT(*) FROM dify_calls GROUP BY app_id").fetchall()
    }
    stats["calls_by_status"] = {
        r[0]: r[1] for r in db.execute("SELECT status, COUNT(*) FROM dify_calls GROUP BY status").fetchall()
    }
    avg = db.execute("SELECT AVG(duration_ms) FROM dify_calls WHERE status='success'").fetchone()[0]
    stats["avg_duration_ms"] = round(avg) if avg else 0

    stats["daily_calls_7d"] = [
        {"date": r[0], "count": r[1]}
        for r in db.execute(
            "SELECT DATE(created_at) as d, COUNT(*) FROM dify_calls WHERE created_at >= DATE('now', '-7 days') GROUP BY d ORDER BY d"
        ).fetchall()
    ]
    stats["daily_projects_7d"] = [
        {"date": r[0], "count": r[1]}
        for r in db.execute(
            "SELECT DATE(created_at) as d, COUNT(*) FROM projects WHERE created_at >= DATE('now', '-7 days') GROUP BY d ORDER BY d"
        ).fetchall()
    ]
    db.close()
    return jsonify(stats)


def _maybe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@app.route("/api/logs", methods=["GET"])
def get_logs():
    page = _int_arg("page", 1, lo=1)
    page_size = _int_arg("page_size", 50, lo=1, hi=500)
    module = request.args.get("module")
    project_id = _maybe_int(request.args.get("project_id"))

    conditions, params = [], []
    if module:
        conditions.append("module = ?")
        params.append(module)
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM logs {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM logs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    return jsonify({"items": [row_to_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})


@app.route("/api/dify-calls", methods=["GET"])
def get_dify_calls():
    page = _int_arg("page", 1, lo=1)
    page_size = _int_arg("page_size", 50, lo=1, hi=500)
    app_id = request.args.get("app_id")
    status = request.args.get("status")
    project_id = _maybe_int(request.args.get("project_id"))

    conditions, params = [], []
    if app_id:
        conditions.append("app_id = ?")
        params.append(app_id.upper())
    if status:
        conditions.append("status = ?")
        params.append(status)
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM dify_calls {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM dify_calls {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    return jsonify({"items": [row_to_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})


# ══════════════════════════════════════════════════════════════════
#  5. 数据导出/导入
# ══════════════════════════════════════════════════════════════════

@app.route("/api/export", methods=["GET"])
@require_admin
def export_all():
    db = get_db()
    cfg = get_config_dict(db)
    rows = db.execute("SELECT * FROM projects ORDER BY id").fetchall()

    # 默认脱敏；显式 ?include_secrets=1 才导出明文 Key
    include_secrets = request.args.get("include_secrets") == "1"
    keys_out = {}
    for aid, col in APP_KEY_MAP.items():
        plain = Config.dify_key_from_env(aid) or decrypt_secret(cfg.get(col, ""))
        keys_out[aid] = plain if include_secrets else mask_key(plain)

    return jsonify({
        "exported_at": datetime.now().isoformat(),
        "secrets_included": include_secrets,
        "config": {
            "base_url": Config.DIFY_BASE_URL or cfg.get("base_url", ""),
            "keys": keys_out,
        },
        "projects": [project_row_to_response(r) for r in rows]
    })


@app.route("/api/import", methods=["POST"])
@require_admin
def import_all():
    body = request.get_json(force=True, silent=True) or {}
    imported = {"config": False, "projects": 0}
    db = get_db()

    if isinstance(body.get("config"), dict):
        c = body["config"]
        keys = c.get("keys", {})

        def _clean(v):
            v = (v or "").strip()
            # 忽略掉从脱敏导出里回填的掩码串
            return "" if (not v or set(v) <= set("*") or "****" in v) else v

        now = datetime.now().isoformat()
        db.execute(
            """UPDATE config SET
               base_url=?, key_a1=?, key_a2=?, key_a3=?, key_a4=?, key_r1=?, key_r2=?, updated_at=?
               WHERE id=1""",
            (c.get("base_url", ""),
             encrypt_secret(_clean(keys.get("A1"))), encrypt_secret(_clean(keys.get("A2"))),
             encrypt_secret(_clean(keys.get("A3"))), encrypt_secret(_clean(keys.get("A4"))),
             encrypt_secret(_clean(keys.get("R1"))), encrypt_secret(_clean(keys.get("R2"))), now)
        )
        imported["config"] = True

    if isinstance(body.get("projects"), list):
        for p in body["projects"]:
            if not isinstance(p, dict):
                continue
            now = datetime.now().isoformat()
            db.execute(
                """INSERT INTO projects
                   (name, activity_type, department, date, target, budget, background, status,
                    a1_data, a2_data, a3_data, a4_data, r1_data, r2_data,
                    versions, feed, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p.get("name", ""), p.get("activity_type", ""), p.get("department", ""),
                 p.get("date", ""), p.get("target", ""), p.get("budget", ""),
                 p.get("background", ""), p.get("status", "draft"),
                 json.dumps(p.get("a1_data", {}), ensure_ascii=False),
                 json.dumps(p.get("a2_data", {}), ensure_ascii=False),
                 json.dumps(p.get("a3_data", {}), ensure_ascii=False),
                 json.dumps(p.get("a4_data", {}), ensure_ascii=False),
                 json.dumps(p.get("r1_data", {}), ensure_ascii=False),
                 json.dumps(p.get("r2_data", {}), ensure_ascii=False),
                 json.dumps(p.get("versions", []), ensure_ascii=False),
                 json.dumps(p.get("feed", []), ensure_ascii=False),
                 p.get("created_at", now), now)
            )
            imported["projects"] += 1

    db.commit()
    add_log(db, "import_data", "system", f"导入完成: config={imported['config']}, projects={imported['projects']}")
    return jsonify({"ok": True, "imported": imported})


# ──────────────────────────── 健康检查 ────────────────────────────

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


# ──────────────────────────── 启动 ────────────────────────────

init_db()

if __name__ == "__main__":
    port = Config.PORT
    debug = Config.DEBUG
    print("=" * 60)
    print("  企业级 AI 应用运营平台 - 后端服务（活动运营场景）")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  API 文档: http://localhost:{port}/api/stats")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=debug)

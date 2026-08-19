"""
AI 活动 SOP 智能运营平台 —— 后端服务
Flask + SQLite，提供项目管理、API 配置、Dify 代理、统计日志等接口。
启动方式: python main.py
"""

import json
import time
import os
from datetime import datetime
from functools import wraps

import httpx
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

from database import get_db, init_db, add_log, add_dify_call

# ──────────────────────────── App 初始化 ────────────────────────────

app = Flask(__name__, static_folder="static", static_url_path="/static")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

APP_KEY_MAP = {
    "A1": "key_a1", "A2": "key_a2", "A3": "key_a3",
    "A4": "key_a4", "R1": "key_r1", "R2": "key_r2"
}


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
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"message": "前端页面未部署。请将 HTML 文件放入 static/ 目录。"})


@app.route("/admin")
def serve_admin():
    html_path = os.path.join(FRONTEND_DIR, "admin.html")
    if os.path.exists(html_path):
        return send_from_directory(FRONTEND_DIR, "admin.html")
    return jsonify({"message": "后台管理页面未部署。请将 admin.html 放入 static/ 目录。"})


# ══════════════════════════════════════════════════════════════════
#  1. API 配置管理
# ══════════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def get_config():
    db = get_db()
    cfg = get_config_dict(db)
    db.close()
    result = {"base_url": cfg.get("base_url", ""), "keys": {}}
    for app_id, col in APP_KEY_MAP.items():
        key = cfg.get(col, "")
        result["keys"][app_id] = {
            "configured": bool(key),
            "masked": (key[:8] + "****" + key[-4:]) if len(key) > 12 else ("****" if key else ""),
            "raw": key
        }
    result["updated_at"] = cfg.get("updated_at", "")
    return jsonify(result)


@app.route("/api/config", methods=["PUT"])
def update_config():
    data = request.get_json(force=True)
    now = datetime.now().isoformat()
    db = get_db()
    db.execute(
        """UPDATE config SET
           base_url=?, key_a1=?, key_a2=?, key_a3=?, key_a4=?, key_r1=?, key_r2=?, updated_at=?
           WHERE id=1""",
        (data.get("base_url", ""),
         data.get("key_a1", ""), data.get("key_a2", ""), data.get("key_a3", ""),
         data.get("key_a4", ""), data.get("key_r1", ""), data.get("key_r2", ""), now)
    )
    db.commit()
    add_log(db, "update_config", "config", f"更新 API 配置，平台地址: {data.get('base_url', '')}")
    db.close()
    return jsonify({"ok": True, "updated_at": now})


@app.route("/api/config/test/<app_id>", methods=["POST"])
def test_connection(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"ok": False, "error": f"无效的应用编号: {app_id}"}), 400

    db = get_db()
    cfg = get_config_dict(db)
    db.close()
    base_url = cfg.get("base_url", "").rstrip("/")
    key = cfg.get(APP_KEY_MAP[app_id], "")

    if not base_url:
        return jsonify({"ok": False, "error": "未配置 Dify 平台地址"})
    if not key:
        return jsonify({"ok": False, "error": f"{app_id} 未配置 API Key"})

    try:
        with httpx.Client(timeout=15, verify=False) as client:
            resp = client.get(f"{base_url}/parameters",
                              headers={"Authorization": f"Bearer {key}"})
            if resp.status_code == 200:
                return jsonify({"ok": True, "app_id": app_id, "status": "connected"})
            else:
                return jsonify({"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
    except httpx.ConnectError as e:
        return jsonify({"ok": False, "error": f"连接失败，请检查 Dify 地址是否正确、后端服务器能否访问该地址: {e}"})
    except httpx.TimeoutException:
        return jsonify({"ok": False, "error": "连接超时（15秒），请检查网络或 Dify 平台是否可达"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/config/test-all", methods=["POST"])
def test_all_connections():
    db = get_db()
    cfg = get_config_dict(db)
    db.close()
    base_url = cfg.get("base_url", "").rstrip("/")
    results = {}
    for app_id, col in APP_KEY_MAP.items():
        key = cfg.get(col, "")
        if not base_url or not key:
            results[app_id] = {"ok": False, "error": "未配置"}
            continue
        try:
            with httpx.Client(timeout=15, verify=False) as client:
                resp = client.get(f"{base_url}/parameters",
                                  headers={"Authorization": f"Bearer {key}"})
                results[app_id] = {"ok": resp.status_code == 200, "status": resp.status_code}
        except Exception as e:
            results[app_id] = {"ok": False, "error": str(e)}
    return jsonify(results)


# ══════════════════════════════════════════════════════════════════
#  2. 项目 CRUD
# ══════════════════════════════════════════════════════════════════

@app.route("/api/projects", methods=["GET"])
def list_projects():
    status = request.args.get("status")
    search = request.args.get("search")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

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
    data = request.get_json(force=True)
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

    data = request.get_json(force=True)
    updates, params = [], []

    for key, value in data.items():
        if key in ("id", "created_at"):
            continue
        if key.endswith("_data") or key in ("versions", "feed"):
            updates.append(f"{key} = ?")
            params.append(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)
        else:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        db.close()
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
def delete_project(project_id):
    db = get_db()
    row = db.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "项目不存在"}), 404
    name = row[0]
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    add_log(db, "delete_project", "project", f"删除项目: {name}", project_id)
    db.close()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════
#  3. Dify 代理
# ══════════════════════════════════════════════════════════════════

@app.route("/api/dify/workflow/<app_id>", methods=["POST"])
def proxy_workflow(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    db = get_db()
    cfg = get_config_dict(db)
    base_url = cfg.get("base_url", "").rstrip("/")
    key = cfg.get(APP_KEY_MAP[app_id], "")

    if not base_url or not key:
        db.close()
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    data = request.get_json(force=True)
    t0 = time.time()
    try:
        with httpx.Client(timeout=300, verify=False) as client:
            resp = client.post(
                f"{base_url}/workflows/run",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"inputs": data.get("inputs", {}), "response_mode": "blocking",
                      "user": data.get("user", "sop-platform")}
            )
            duration = int((time.time() - t0) * 1000)
            result = resp.json()
            add_dify_call(db, app_id, "workflow",
                          json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000],
                          json.dumps(result, ensure_ascii=False)[:5000],
                          duration, "success", "", data.get("project_id"))
            db.close()
            return jsonify(result)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        add_dify_call(db, app_id, "workflow",
                      json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000],
                      "", duration, "error", str(e), data.get("project_id"))
        db.close()
        return jsonify({"error": f"Dify 调用失败: {str(e)}"}), 502


@app.route("/api/dify/workflow-stream/<app_id>", methods=["POST"])
def proxy_workflow_stream(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    db = get_db()
    cfg = get_config_dict(db)
    base_url = cfg.get("base_url", "").rstrip("/")
    key = cfg.get(APP_KEY_MAP[app_id], "")
    db.close()

    if not base_url or not key:
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    data = request.get_json(force=True)

    def generate():
        t0 = time.time()
        try:
            with httpx.Client(timeout=300, verify=False) as client:
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
            duration = int((time.time() - t0) * 1000)
            db2 = get_db()
            add_dify_call(db2, app_id, "workflow_stream",
                          json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000],
                          "[stream]", duration, "success", "", data.get("project_id"))
            db2.close()
        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            db2 = get_db()
            add_dify_call(db2, app_id, "workflow_stream",
                          json.dumps(data.get("inputs", {}), ensure_ascii=False)[:2000],
                          "", duration, "error", str(e), data.get("project_id"))
            db2.close()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/dify/chat/<app_id>", methods=["POST"])
def proxy_chat(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    db = get_db()
    cfg = get_config_dict(db)
    base_url = cfg.get("base_url", "").rstrip("/")
    key = cfg.get(APP_KEY_MAP[app_id], "")

    if not base_url or not key:
        db.close()
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    data = request.get_json(force=True)
    t0 = time.time()
    body = {
        "query": data.get("query", ""),
        "inputs": data.get("inputs", {}),
        "response_mode": "blocking",
        "user": data.get("user", "sop-platform")
    }
    if data.get("conversation_id"):
        body["conversation_id"] = data["conversation_id"]

    try:
        with httpx.Client(timeout=300, verify=False) as client:
            resp = client.post(
                f"{base_url}/chat-messages",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body
            )
            duration = int((time.time() - t0) * 1000)
            result = resp.json()
            add_dify_call(db, app_id, "chat",
                          json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000],
                          json.dumps(result, ensure_ascii=False)[:5000],
                          duration, "success", "", data.get("project_id"))
            db.close()
            return jsonify(result)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        add_dify_call(db, app_id, "chat",
                      json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000],
                      "", duration, "error", str(e), data.get("project_id"))
        db.close()
        return jsonify({"error": f"Dify 调用失败: {str(e)}"}), 502


@app.route("/api/dify/chat-stream/<app_id>", methods=["POST"])
def proxy_chat_stream(app_id):
    app_id = app_id.upper()
    if app_id not in APP_KEY_MAP:
        return jsonify({"error": f"无效的应用编号: {app_id}"}), 400

    db = get_db()
    cfg = get_config_dict(db)
    base_url = cfg.get("base_url", "").rstrip("/")
    key = cfg.get(APP_KEY_MAP[app_id], "")
    db.close()

    if not base_url or not key:
        return jsonify({"error": f"请先配置 {app_id} 的 API 连接信息"}), 400

    data = request.get_json(force=True)
    body = {
        "query": data.get("query", ""),
        "inputs": data.get("inputs", {}),
        "response_mode": "streaming",
        "user": data.get("user", "sop-platform")
    }
    if data.get("conversation_id"):
        body["conversation_id"] = data["conversation_id"]

    def generate():
        t0 = time.time()
        try:
            with httpx.Client(timeout=300, verify=False) as client:
                with client.stream(
                    "POST",
                    f"{base_url}/chat-messages",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=body
                ) as resp:
                    for line in resp.iter_lines():
                        if line.startswith("data:"):
                            yield f"{line}\n\n"
            duration = int((time.time() - t0) * 1000)
            db2 = get_db()
            add_dify_call(db2, app_id, "chat_stream",
                          json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000],
                          "[stream]", duration, "success", "", data.get("project_id"))
            db2.close()
        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            db2 = get_db()
            add_dify_call(db2, app_id, "chat_stream",
                          json.dumps({"query": data.get("query", "")}, ensure_ascii=False)[:2000],
                          "", duration, "error", str(e), data.get("project_id"))
            db2.close()
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


@app.route("/api/logs", methods=["GET"])
def get_logs():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    module = request.args.get("module")
    project_id = request.args.get("project_id")

    conditions, params = [], []
    if module:
        conditions.append("module = ?")
        params.append(module)
    if project_id:
        conditions.append("project_id = ?")
        params.append(int(project_id))
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM logs {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM logs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    db.close()
    return jsonify({"items": [row_to_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})


@app.route("/api/dify-calls", methods=["GET"])
def get_dify_calls():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    app_id = request.args.get("app_id")
    status = request.args.get("status")
    project_id = request.args.get("project_id")

    conditions, params = [], []
    if app_id:
        conditions.append("app_id = ?")
        params.append(app_id.upper())
    if status:
        conditions.append("status = ?")
        params.append(status)
    if project_id:
        conditions.append("project_id = ?")
        params.append(int(project_id))
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM dify_calls {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM dify_calls {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    db.close()
    return jsonify({"items": [row_to_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})


# ══════════════════════════════════════════════════════════════════
#  5. 数据导出/导入
# ══════════════════════════════════════════════════════════════════

@app.route("/api/export", methods=["GET"])
def export_all():
    db = get_db()
    cfg = get_config_dict(db)
    rows = db.execute("SELECT * FROM projects ORDER BY id").fetchall()
    db.close()

    return jsonify({
        "exported_at": datetime.now().isoformat(),
        "config": {
            "base_url": cfg.get("base_url", ""),
            "keys": {aid: cfg.get(col, "") for aid, col in APP_KEY_MAP.items()}
        },
        "projects": [project_row_to_response(r) for r in rows]
    })


@app.route("/api/import", methods=["POST"])
def import_all():
    body = request.get_json(force=True)
    imported = {"config": False, "projects": 0}
    db = get_db()

    if "config" in body:
        c = body["config"]
        keys = c.get("keys", {})
        now = datetime.now().isoformat()
        db.execute(
            """UPDATE config SET
               base_url=?, key_a1=?, key_a2=?, key_a3=?, key_a4=?, key_r1=?, key_r2=?, updated_at=?
               WHERE id=1""",
            (c.get("base_url", ""),
             keys.get("A1", ""), keys.get("A2", ""), keys.get("A3", ""),
             keys.get("A4", ""), keys.get("R1", ""), keys.get("R2", ""), now)
        )
        imported["config"] = True

    if "projects" in body:
        for p in body["projects"]:
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
    db.close()
    return jsonify({"ok": True, "imported": imported})


# ──────────────────────────── 启动 ────────────────────────────

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("=" * 60)
    print("  AI 活动 SOP 智能运营平台 - 后端服务")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  API 文档: http://localhost:{port}/api/stats")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=debug)

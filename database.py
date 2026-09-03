"""
SQLite 数据库模块 —— 企业级 AI 应用运营平台（活动运营场景）
同步 sqlite3 操作，所有表自动初始化。

config 表里的 Dify API Key 支持透明加密：
  - 设置 APP_SECRET_KEY 时，写入加 "enc:v1:" 前缀的 Fernet 密文
  - 读取时自动解密；无前缀的历史明文原样返回（平滑兼容）
"""

import sqlite3
from datetime import datetime

from config import Config

DB_PATH = Config.DB_PATH

_ENC_PREFIX = "enc:v1:"


# ──────────────────────────── 加密 ────────────────────────────

def _fernet():
    """按需构造 Fernet；未配置 APP_SECRET_KEY 时返回 None。"""
    if not Config.APP_SECRET_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("已设置 APP_SECRET_KEY，但未安装 cryptography 依赖") from e
    return Fernet(Config.APP_SECRET_KEY.encode())


def encrypt_secret(plain: str) -> str:
    """加密一个密钥字符串；空值或未启用加密时原样返回。"""
    if not plain:
        return ""
    f = _fernet()
    if f is None:
        return plain
    if plain.startswith(_ENC_PREFIX):
        return plain
    return _ENC_PREFIX + f.encrypt(plain.encode()).decode()


def decrypt_secret(stored: str) -> str:
    """解密存储值；非密文（历史明文）原样返回。"""
    if not stored or not stored.startswith(_ENC_PREFIX):
        return stored or ""
    f = _fernet()
    if f is None:  # 有密文却没密钥，无法解密
        return ""
    try:
        return f.decrypt(stored[len(_ENC_PREFIX):].encode()).decode()
    except Exception:
        return ""


# ──────────────────────────── 连接 ────────────────────────────

def get_db():
    """获取一个新的数据库连接（连接的关闭由调用方 / Flask teardown 负责）。"""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    """初始化数据库，创建全部表并设置 WAL 模式。"""
    db = get_db()
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            base_url TEXT NOT NULL DEFAULT '',
            key_a1 TEXT NOT NULL DEFAULT '',
            key_a2 TEXT NOT NULL DEFAULT '',
            key_a3 TEXT NOT NULL DEFAULT '',
            key_a4 TEXT NOT NULL DEFAULT '',
            key_r1 TEXT NOT NULL DEFAULT '',
            key_r2 TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO config (id, updated_at) VALUES (1, '');

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            activity_type TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL DEFAULT '',
            budget TEXT NOT NULL DEFAULT '',
            background TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            a1_data TEXT NOT NULL DEFAULT '{}',
            a2_data TEXT NOT NULL DEFAULT '{}',
            a3_data TEXT NOT NULL DEFAULT '{}',
            a4_data TEXT NOT NULL DEFAULT '{}',
            r1_data TEXT NOT NULL DEFAULT '{}',
            r2_data TEXT NOT NULL DEFAULT '{}',
            versions TEXT NOT NULL DEFAULT '[]',
            feed TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            action TEXT NOT NULL,
            module TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS dify_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            app_id TEXT NOT NULL,
            call_type TEXT NOT NULL DEFAULT 'workflow',
            input_data TEXT NOT NULL DEFAULT '{}',
            output_data TEXT NOT NULL DEFAULT '',
            duration_ms INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'success',
            error_msg TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_projects_status   ON projects(status);
        CREATE INDEX IF NOT EXISTS idx_projects_updated   ON projects(updated_at);
        CREATE INDEX IF NOT EXISTS idx_logs_created       ON logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_logs_project       ON logs(project_id);
        CREATE INDEX IF NOT EXISTS idx_dify_created       ON dify_calls(created_at);
        CREATE INDEX IF NOT EXISTS idx_dify_app           ON dify_calls(app_id);
        CREATE INDEX IF NOT EXISTS idx_dify_project       ON dify_calls(project_id);
    """)
    db.commit()
    db.close()


def add_log(db, action, module="", detail="", project_id=None):
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO logs (project_id, action, module, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (project_id, action, module, detail, now)
    )
    db.commit()


def add_dify_call(db, app_id, call_type, input_data, output_data,
                   duration_ms, status="success", error_msg="", project_id=None):
    now = datetime.now().isoformat()
    db.execute(
        """INSERT INTO dify_calls
           (project_id, app_id, call_type, input_data, output_data, duration_ms, status, error_msg, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, app_id, call_type, input_data, output_data, duration_ms, status, error_msg, now)
    )
    db.commit()

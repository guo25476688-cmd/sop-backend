"""
SQLite 数据库模块 —— AI 活动 SOP 智能运营平台
同步 sqlite3 操作，所有表自动初始化。
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("SOP_DB_PATH", os.path.join(os.path.dirname(__file__), "sop_platform.db"))


def get_db():
    """获取数据库连接"""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    """初始化数据库，创建全部表"""
    db = get_db()
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

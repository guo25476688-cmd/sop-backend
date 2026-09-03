"""
集中配置 —— 全部来自环境变量，遵循 12-Factor。
本地开发可放到 .env（见 .env.example），由 python-dotenv 自动加载。
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv 是可选依赖，缺失不影响生产（生产直接注入环境变量）
    pass

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_IDS = ["A1", "A2", "A3", "A4", "R1", "R2"]


def _bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # ── 服务 ──
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = _bool("FLASK_DEBUG")
    # 单个请求体上限，防止超大 payload 打爆内存
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(4 * 1024 * 1024)))

    # ── 数据库 ──
    DB_PATH = os.getenv("SOP_DB_PATH", os.path.join(_BASE_DIR, "sop_platform.db"))

    # ── 密钥加密 ──
    # 设置后，写入 config 表的 Dify API Key 会用 Fernet 加密存储。
    # 不设置则明文存储（仅建议本地开发），启动时会打印告警。
    APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "").strip()

    # ── 管理面鉴权 ──
    # 设置后，/admin 页面与所有写接口需要 HTTP Basic（用户名任意，密码=该值）。
    # 不设置则为开放的开发模式，响应头会带 X-Auth-Warning。
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

    # ── Dify 连接 ──
    # 若在环境变量里提供，则作为权威来源，覆盖 config 表，且不可在 UI 修改。
    DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "").strip().rstrip("/")
    DIFY_VERIFY_SSL = _bool("DIFY_VERIFY_SSL", "1")  # 默认校验证书；自建 Dify 用自签名证书时设为 0
    DIFY_TIMEOUT = int(os.getenv("DIFY_TIMEOUT", "300"))

    @staticmethod
    def dify_key_from_env(app_id: str) -> str:
        return os.getenv(f"DIFY_KEY_{app_id.upper()}", "").strip()

    @classmethod
    def env_keys(cls) -> dict:
        """返回由环境变量提供的 Key（app_id -> key），只含非空项。"""
        return {aid: cls.dify_key_from_env(aid) for aid in APP_IDS if cls.dify_key_from_env(aid)}

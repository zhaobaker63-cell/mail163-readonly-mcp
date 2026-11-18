"""Non-sensitive configuration loading and strict read-only validation."""
from __future__ import annotations

import json
from pathlib import Path
import re


class ConfigError(RuntimeError):
    pass


DEFAULT_ALLOWED_FOLDERS = ["INBOX", "已发送"]
DEFAULT_CREDENTIAL_TARGET = "Mail163ReadOnly"
DEFAULT_IMAP_PORT = 993
DEFAULT_MAX_MESSAGE_BYTES = 10485760  # 10 MB
DEFAULT_MAX_BODY_CHARS = 16000        # 防止超大邮件正文刷爆模型上下文
DEFAULT_DATE_WINDOW_MONTHS = 24       # 默认限制过去 24 个月


def load_config(path: str | Path | None = None) -> dict:
    """加载配置并严格校验，决不从文件读取密码或授权码。"""
    if path is None:
        # 默认优先寻找当前工作目录下的 config.json，其次在用户 AppData
        local_p = Path("config.json")
        if local_p.is_file():
            source = local_p.resolve()
        else:
            appdata = Path.home() / ".mail163-mcp" / "config.json"
            if appdata.is_file():
                source = appdata.resolve()
            else:
                raise ConfigError("未找到配置文件。请先运行一键配置向导。")
    else:
        source = Path(path).resolve()

    if not source.is_file():
        raise ConfigError(f"配置文件不存在: {source}")
    if source.stat().st_size > 65536:
        raise ConfigError("配置文件异常偏大")

    try:
        raw = json.loads(source.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise ConfigError(f"配置文件 JSON 格式错误: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("配置文件必须是 JSON 对象")

    # 拒绝任何明文密码/授权码出现在配置中
    for forbidden in ("password", "secret", "auth_code", "token", "credential"):
        if forbidden in raw:
            raise ConfigError(f"安全违规：配置文件严禁包含敏感凭证字段 '{forbidden}'，密码只能保存在系统凭据管理器中")

    mailbox = raw.get("mailbox")
    if not isinstance(mailbox, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", mailbox):
        raise ConfigError("mailbox 必须是合法的邮箱地址")

    imap_host = raw.get("imap_host")
    if not isinstance(imap_host, str) or not imap_host or len(imap_host) > 255:
        raise ConfigError("imap_host 不能为空")

    imap_port = int(raw.get("imap_port", DEFAULT_IMAP_PORT))
    if not (1 <= imap_port <= 65535):
        raise ConfigError("imap_port 必须在 1-65535 范围内")

    allowed_folders = raw.get("allowed_folders", DEFAULT_ALLOWED_FOLDERS)
    if not isinstance(allowed_folders, list) or not all(isinstance(f, str) and f for f in allowed_folders):
        raise ConfigError("allowed_folders 必须是非空字符串数组")

    return {
        "config_path": str(source),
        "mailbox": mailbox,
        "imap_host": imap_host,
        "imap_port": imap_port,
        "allowed_folders": allowed_folders,
        "credential_target": str(raw.get("credential_target", DEFAULT_CREDENTIAL_TARGET)),
        "max_message_bytes": int(raw.get("max_message_bytes", DEFAULT_MAX_MESSAGE_BYTES)),
        "max_body_chars": int(raw.get("max_body_chars", DEFAULT_MAX_BODY_CHARS)),
        "date_window_months": int(raw.get("date_window_months", DEFAULT_DATE_WINDOW_MONTHS)),
    }

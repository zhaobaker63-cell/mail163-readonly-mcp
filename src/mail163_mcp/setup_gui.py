"""One-click configuration wizard (GUI + CLI fallback, zero-dependency)."""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

from .config import DEFAULT_ALLOWED_FOLDERS, DEFAULT_CREDENTIAL_TARGET, DEFAULT_IMAP_PORT
from .credentials import write_credential
from .imap_reader import MailReader


COMMON_163_HOSTS = {
    "qiye.163.com": "imap.qiye.163.com",
    "hw.qiye.163.com": "hwimap.qiye.163.com",
}


def guess_imap_host(mailbox: str) -> str:
    domain = mailbox.split("@")[-1].lower() if "@" in mailbox else ""
    return "imap.qiye.163.com"  # 网易企业邮箱默认主节点


def run_test_connection(mailbox: str, host: str, port: int, secret: str) -> tuple[bool, str]:
    """使用 EXAMINE 只读方式快速测试邮箱认证。"""
    cfg = {
        "mailbox": mailbox,
        "imap_host": host,
        "imap_port": port,
        "allowed_folders": ["INBOX"],
        "max_message_bytes": 10485760,
        "max_body_chars": 8000,
        "date_window_months": 24,
    }
    try:
        reader = MailReader(cfg, lambda: secret)
        folders = reader.list_folders()
        return True, f"连接成功！可读文件夹数: {len(folders)}"
    except Exception as e:
        return False, f"连接或认证失败: {str(e)}"


def run_setup(config_dir: Path | None = None) -> None:
    target_dir = config_dir or (Path.home() / ".mail163-mcp")
    target_dir.mkdir(parents=True, exist_ok=True)
    config_file = target_dir / "config.json"

    # 如果存在已配置信息，提供默认值
    default_mailbox = ""
    default_host = "imap.qiye.163.com"
    if config_file.is_file():
        try:
            old = json.loads(config_file.read_text(encoding="utf-8"))
            default_mailbox = old.get("mailbox", "")
            default_host = old.get("imap_host", "imap.qiye.163.com")
        except Exception:
            pass

    print("\n" + "=" * 60)
    print(" 📧 网易163企业邮箱只读 MCP · 一键配置向导")
    print("=" * 60)
    print("说明：")
    print(" 1. 邮箱授权码将直接存入操作系统的系统凭据管理器（安全加密）。")
    print(" 2. 任何本地配置文件、日志、代码中均决不保存明文密码。")
    print(" 3. 配置完成后将直接生成各 Agent 平台的快速接入配置。")
    print("-" * 60)

    # 1. 邮箱地址
    mailbox = input(f"请输入你的企业邮箱地址 [{default_mailbox}]: ").strip() or default_mailbox
    while not ("@" in mailbox and "." in mailbox):
        mailbox = input("邮箱格式不正确，请重新输入: ").strip()

    # 2. IMAP 主机
    suggested_host = default_host or guess_imap_host(mailbox)
    host = input(f"请输入 IMAP 服务器地址 [{suggested_host}]: ").strip() or suggested_host

    # 3. 授权码
    print("请输入企业邮箱客户端授权密码（输入时屏幕不显示字符，输完按回车）:")
    secret = getpass.getpass("授权码: ").strip()
    while not secret:
        secret = getpass.getpass("授权码不能为空，请重新输入: ").strip()

    print("\n正在安全测试与网易服务器的只读连接...")
    ok, msg = run_test_connection(mailbox, host, DEFAULT_IMAP_PORT, secret)
    if not ok:
        print(f"\n❌ 测试失败：{msg}")
        print("请检查邮箱地址、IMAP服务器或授权码是否正确。未保存任何更改。")
        return

    print(f"✅ {msg}")

    # 保存凭证与非敏感配置
    write_credential(DEFAULT_CREDENTIAL_TARGET, secret, user_name=mailbox)
    secret = None  # 擦除内存引用

    cfg_payload = {
        "mailbox": mailbox,
        "imap_host": host,
        "imap_port": DEFAULT_IMAP_PORT,
        "allowed_folders": DEFAULT_ALLOWED_FOLDERS,
        "credential_target": DEFAULT_CREDENTIAL_TARGET,
        "max_message_bytes": 10485760,
        "max_body_chars": 16000,
        "date_window_months": 24,
    }
    config_file.write_text(json.dumps(cfg_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # 同时在当前工作目录下也保留一份副本以便本地开发
    try:
        Path("config.json").write_text(json.dumps(cfg_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("🎉 配置完成！授权码已安全加密入库。")
    print(f"📄 非敏感配置文件已写入: {config_file}")
    print("=" * 60)
    print_agent_configs(config_file)


def print_agent_configs(config_file: Path) -> None:
    python_cmd = sys.executable
    print("\n=== 各平台一键接入配置代码（直接复制粘贴即可） ===")

    # 1. Codex
    print("\n【1. Codex 配置】(~/.codex/config.toml):")
    print(f"""[mcp_servers.mail163]
command = "{python_cmd.replace(chr(92), chr(92)*2)}"
args = ["-m", "mail163_mcp", "serve", "--config", "{str(config_file).replace(chr(92), chr(92)*2)}"]
""")

    # 2. Accio / Claude Desktop / Cursor
    print("【2. Accio / Claude Desktop / Cursor 配置】(mcpServers JSON):")
    json_snippet = {
        "mcpServers": {
            "mail163": {
                "command": python_cmd,
                "args": ["-m", "mail163_mcp", "serve", "--config", str(config_file)]
            }
        }
    }
    print(json.dumps(json_snippet, indent=2, ensure_ascii=False))

    # 3. WorkBuddy
    print("\n【3. WorkBuddy 配置】(工作空间设置 -> MCP Servers):")
    print(f"命令: {python_cmd}")
    print(f"参数: -m mail163_mcp serve --config \"{config_file}\"")

    # 4. DeepSeek Harness
    print("\n【4. DeepSeek Harness 配置】:")
    print(f"可直接在启动配置中指定 stdio: {python_cmd} -m mail163_mcp serve --config \"{config_file}\"")
    print("=" * 60 + "\n")

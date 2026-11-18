"""Main command-line entry for mail163-readonly-mcp."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .credentials import read_credential
from .imap_reader import MailReader
from .server import MCPServer
from .setup_gui import run_setup
from .tools import ToolDispatcher


def cmd_serve(args):
    config = load_config(args.config)
    target = config["credential_target"]
    reader = MailReader(config, lambda: read_credential(target))
    dispatcher = ToolDispatcher(reader)
    server = MCPServer(dispatcher)
    server.run_stdio()


def cmd_check(args):
    try:
        config = load_config(args.config)
        target = config["credential_target"]
        secret = read_credential(target)
        reader = MailReader(config, lambda: secret)
        folders = reader.list_folders()
        print(f"✅ 连接验证成功！")
        print(f"• 邮箱: {config['mailbox']}")
        print(f"• 主机: {config['imap_host']}:{config['imap_port']}")
        print(f"• 可读文件夹: {[f['name'] for f in folders]}")
    except Exception as e:
        print(f"❌ 验证失败: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_setup(args):
    run_setup(Path(args.dir) if args.dir else None)


def main():
    parser = argparse.ArgumentParser(description="网易163企业邮箱只读 MCP 服务")
    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # serve
    serve_parser = subparsers.add_parser("serve", help="启动 stdio MCP 服务（供 Agent 客户端调用）")
    serve_parser.add_argument("--config", help="配置文件路径（可选，默认自动寻找）")

    # check
    check_parser = subparsers.add_parser("check", help="自检邮箱只读连通性与凭证状态")
    check_parser.add_argument("--config", help="配置文件路径（可选）")

    # setup
    setup_parser = subparsers.add_parser("setup", help="运行交互式一键配置向导")
    setup_parser.add_argument("--dir", help="指定配置文件保存目录（可选）")

    args = parser.parse_args()

    if args.subcommand == "serve":
        cmd_serve(args)
    elif args.subcommand == "check":
        cmd_check(args)
    elif args.subcommand == "setup":
        cmd_setup(args)
    else:
        # 默认行为：如果有配置则尝试 check，否则运行 setup
        try:
            cfg = load_config()
            cmd_check(argparse.Namespace(config=cfg.get("config_path")))
        except Exception:
            cmd_setup(argparse.Namespace(dir=None))


if __name__ == "__main__":
    main()

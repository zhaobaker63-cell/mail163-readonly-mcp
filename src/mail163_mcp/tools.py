"""MCP Tool definitions and handler implementations (Lean, Token-saving schemas)."""
from __future__ import annotations

import base64
from pathlib import Path
import tempfile

from .imap_reader import MailReader


# 5 个核心只读工具定义
TOOLS = [
    {
        "name": "mail_list_folders",
        "description": "列出企业邮箱中已授权的只读文件夹（如 INBOX、已发送）。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "mail_search",
        "description": "搜索指定文件夹内的邮件。仅返回邮件元数据分页列表（UID、主题、发件人、收件人、时间、大小），不带正文，极低Token消耗。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "文件夹名称，如 'INBOX' 或 '已发送'。",
                },
                "query": {
                    "type": "string",
                    "description": "可选过滤关键词（主题或正文关键词）。",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数，默认 30，最大 200。",
                    "default": 30,
                },
                "cursor": {
                    "type": "integer",
                    "description": "分页游标（上一页返回的 next_cursor UID）。",
                },
            },
            "required": ["folder"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mail_get_message",
        "description": "读取单封邮件详情。返回结构化标头、纯文本正文（超长自动截断保护）和附件元数据清单。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "邮件所在文件夹，如 'INBOX'。",
                },
                "uid": {
                    "type": "integer",
                    "description": "邮件的 IMAP UID。",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "正文最大返回字符数，默认 8000 字符，超出截断以防上下文溢出。",
                    "default": 8000,
                },
            },
            "required": ["folder", "uid"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mail_get_attachment",
        "description": "下载提取指定邮件的附件。默认落盘到本地临时文件并返回路径，避免大文件污染上下文；可选以 base64 形式返回。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "邮件所在文件夹。",
                },
                "uid": {
                    "type": "integer",
                    "description": "邮件的 IMAP UID。",
                },
                "part": {
                    "type": "integer",
                    "description": "附件在邮件中的部件编号（从 mail_get_message 的 attachments 列表中获取）。",
                },
                "as_base64": {
                    "type": "boolean",
                    "description": "是否以 base64 字符串直接返回内容，默认为 false（推荐 false，返回临时文件路径）。",
                    "default": False,
                },
            },
            "required": ["folder", "uid", "part"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mail_get_thread",
        "description": "根据 Message-ID 追踪并聚合整条往返往来邮件线程，按时间升序返回上下文对话链。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "起始文件夹名称。",
                },
                "message_id": {
                    "type": "string",
                    "description": "目标邮件的 Message-ID，如 '<xxx@mail.com>'。",
                },
                "max_messages": {
                    "type": "integer",
                    "description": "线程最多返回消息数，默认 20，防超大线程爆仓。",
                    "default": 20,
                },
            },
            "required": ["folder", "message_id"],
            "additionalProperties": False,
        },
    },
]


class ToolDispatcher:
    def __init__(self, reader: MailReader):
        self._reader = reader

    def call_tool(self, name: str, args: dict) -> dict:
        if name == "mail_list_folders":
            folders = self._reader.list_folders()
            return {"folders": folders}

        elif name == "mail_search":
            return self._reader.search_messages(
                folder=str(args["folder"]),
                query=args.get("query"),
                limit=int(args.get("limit", 30)),
                cursor=args.get("cursor"),
            )

        elif name == "mail_get_message":
            return self._reader.read_message(
                folder=str(args["folder"]),
                uid=int(args["uid"]),
                max_chars=int(args.get("max_chars", 8000)),
            )

        elif name == "mail_get_attachment":
            fn, ct, payload = self._reader.fetch_attachment_bytes(
                folder=str(args["folder"]),
                uid=int(args["uid"]),
                part_id=int(args["part"]),
            )
            as_b64 = bool(args.get("as_base64", False))
            if as_b64:
                return {
                    "filename": fn,
                    "content_type": ct,
                    "size_bytes": len(payload),
                    "base64": base64.b64encode(payload).decode("ascii"),
                }
            else:
                # 写入安全临时文件
                temp_dir = Path(tempfile.gettempdir()) / "mail163_mcp_attachments"
                temp_dir.mkdir(parents=True, exist_ok=True)
                # 清洗文件名防止路径穿越
                safe_name = "".join(c for c in fn if c.isalnum() or c in "._- ") or "file.bin"
                target_file = temp_dir / f"{args['uid']}_{args['part']}_{safe_name}"
                target_file.write_bytes(payload)
                return {
                    "filename": fn,
                    "content_type": ct,
                    "size_bytes": len(payload),
                    "temp_path": str(target_file),
                }

        elif name == "mail_get_thread":
            thread = self._reader.get_thread_by_message_id(
                folder=str(args["folder"]),
                message_id=str(args["message_id"]),
                max_messages=int(args.get("max_messages", 20)),
            )
            return {
                "message_id": args["message_id"],
                "thread_length": len(thread),
                "messages": thread,
            }

        else:
            raise ValueError(f"未知工具: {name}")

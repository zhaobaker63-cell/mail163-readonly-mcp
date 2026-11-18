"""Standard MCP Protocol Server (stdio transport default, zero external dependencies)."""
from __future__ import annotations

import json
import sys
import traceback

from .tools import TOOLS, ToolDispatcher


MCP_PROTOCOL_VERSIONS = ["2024-11-05", "2024-10-07"]


class MCPServer:
    def __init__(self, dispatcher: ToolDispatcher):
        self._dispatcher = dispatcher

    def handle_request(self, req: dict) -> dict | None:
        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "mail163-readonly-mcp",
                        "version": "0.2.0"
                    }
                }
            }

        elif method in ("notifications/initialized", "initialized"):
            return None  # MCP 通知不需要回复响应

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS
                }
            }

        elif method == "tools/call":
            params = req.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}

            try:
                res_obj = self._dispatcher.call_tool(name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res_obj, ensure_ascii=False, indent=2)
                            }
                        ],
                        "isError": False
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error calling {name}: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    def run_stdio(self):
        """标准 stdio 运行循环，兼容 Codex, Accio, Cursor, WorkBuddy, DeepSeek 等。"""
        # 强制将 stdin/stdout 设置为 UTF-8 编码，防止 Windows 默认 ANSI 乱码
        if sys.platform == "win32":
            import os
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

        reader = sys.stdin.buffer
        writer = sys.stdout.buffer

        while True:
            line = reader.readline()
            if not line:
                break
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                payload = json.loads(line_str)
                resp = self.handle_request(payload)
                if resp is not None:
                    out_bytes = json.dumps(resp, ensure_ascii=False).encode("utf-8") + b"\n"
                    writer.write(out_bytes)
                    writer.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                writer.write(json.dumps(err_resp).encode("utf-8") + b"\n")
                writer.flush()

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mail163_mcp.server import MCPServer
from mail163_mcp.tools import TOOLS, ToolDispatcher


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.mock_reader = MagicMock()
        self.mock_reader.list_folders.return_value = [{"name": "INBOX", "flags": []}]
        self.mock_reader.search_messages.return_value = {
            "folder": "INBOX",
            "total_matched": 1,
            "has_more": False,
            "next_cursor": None,
            "messages": [{"uid": 101, "subject": "Test", "from": "a@b.com", "to": "c@d.com", "date": "today", "size": 100}]
        }
        self.mock_reader.read_message.return_value = {
            "folder": "INBOX",
            "uid": 101,
            "subject": "Test",
            "from": "a@b.com",
            "to": "c@d.com",
            "body_text": "Hello world",
            "body_truncated": False,
            "attachments": []
        }
        self.mock_reader.fetch_attachment_bytes.return_value = ("quote.pdf", "application/pdf", b"%PDF-test")
        self.mock_reader.get_thread_by_message_id.return_value = [{"uid": 101, "subject": "Thread item"}]

        self.dispatcher = ToolDispatcher(self.mock_reader)
        self.server = MCPServer(self.dispatcher)

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = self.server.handle_request(req)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "mail163-readonly-mcp")

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        resp = self.server.handle_request(req)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(len(names), 5)
        self.assertIn("mail_list_folders", names)
        self.assertIn("mail_search", names)
        self.assertIn("mail_get_message", names)
        self.assertIn("mail_get_attachment", names)
        self.assertIn("mail_get_thread", names)

    def test_call_search(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "mail_search", "arguments": {"folder": "INBOX"}}
        }
        resp = self.server.handle_request(req)
        self.assertFalse(resp["result"]["isError"])
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["total_matched"], 1)

    def test_call_get_attachment_temp_path(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "mail_get_attachment", "arguments": {"folder": "INBOX", "uid": 101, "part": 1, "as_base64": False}}
        }
        resp = self.server.handle_request(req)
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("temp_path", payload)
        self.assertEqual(payload["filename"], "quote.pdf")


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mail163_mcp.config import ConfigError, load_config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_file = Path(self.tmp.name) / "config.json"

    def test_reject_password_in_config(self):
        self.cfg_file.write_text(json.dumps({"mailbox": "a@b.com", "password": "123"}), encoding="utf-8")
        with self.assertRaises(ConfigError):
            load_config(self.cfg_file)

    def test_valid_config(self):
        payload = {
            "mailbox": "user@test-company.com",
            "imap_host": "imap.qiye.163.com",
            "imap_port": 993,
            "allowed_folders": ["INBOX"]
        }
        self.cfg_file.write_text(json.dumps(payload), encoding="utf-8")
        cfg = load_config(self.cfg_file)
        self.assertEqual(cfg["mailbox"], "user@test-company.com")
        self.assertEqual(cfg["credential_target"], "Mail163ReadOnly")


if __name__ == "__main__":
    unittest.main()

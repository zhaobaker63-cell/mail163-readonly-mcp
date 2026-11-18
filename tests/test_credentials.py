import os
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from mail163_mcp.credentials import SecurityError, delete_credential, read_credential, write_credential


class TestCredentials(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_win32_cred_roundtrip(self):
        target = f"Mail163Test_{uuid.uuid4().hex[:8]}"
        secret = "SECRET_12345678_TEST"

        try:
            write_credential(target, secret)
            got = read_credential(target)
            self.assertEqual(got, secret)
        finally:
            delete_credential(target)

        with self.assertRaises(SecurityError):
            read_credential(target)


if __name__ == "__main__":
    unittest.main()

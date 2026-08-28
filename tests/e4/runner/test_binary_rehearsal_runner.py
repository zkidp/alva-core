import tempfile
import unittest
from pathlib import Path

from binary_rehearsal_runner import TEXT, read_exact_utf8, script_for


class BinaryRehearsalRunnerTests(unittest.TestCase):
    def test_same_content_write_preserves_crlf_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "main.alva"
            source.write_bytes(b"fn main() {\r\n}\r\n")

            content = read_exact_utf8(source)
            script = script_for(TEXT, ["src/main.alva"], content)
            write = next(item for item in script if item.get("tool") == "write_file")

            self.assertEqual(content, "fn main() {\r\n}\r\n")
            self.assertEqual(write["args"]["content"].encode("utf-8"), source.read_bytes())


if __name__ == "__main__":
    unittest.main()

"""Offline checks for the new onboarding pages, not whole-repository link crawling."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
PAGES = ("README.md", "README.zh-CN.md", "docs/getting-started.md", "docs/development-preview.md")
VERSION = "v0.14.1-preview.2"


def slug(heading):
    heading = re.sub(r"<[^>]*>|[`*_]", "", heading).strip().lower()
    return re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")


class HomepageTests(unittest.TestCase):
    def test_local_links_images_and_fragments(self):
        for name in PAGES:
            page = ROOT / name
            text = page.read_text(encoding="utf-8")
            links = re.findall(r"\]\(([^)\s]+)\)", text)
            links += re.findall(r'<img\s[^>]*src="([^"]+)"', text)
            for link in links:
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc:
                    continue
                target = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
                self.assertTrue(target.is_relative_to(ROOT), (name, link))
                self.assertTrue(target.exists(), (name, link))
                if parsed.fragment and target.suffix == ".md":
                    headings = re.findall(r"^#{1,6}\s+(.+)$", target.read_text(encoding="utf-8"), re.M)
                    self.assertIn(unquote(parsed.fragment), {slug(h) for h in headings}, (name, link))

    def test_release_and_language_entry_points(self):
        english = (ROOT / PAGES[0]).read_text(encoding="utf-8")
        chinese = (ROOT / PAGES[1]).read_text(encoding="utf-8")
        self.assertIn("(README.zh-CN.md)", english)
        self.assertIn("(README.md)", chinese)
        for text in (english, chinese):
            fences = re.findall(r"^```[^\n]*$", text, re.M)
            self.assertGreaterEqual(len(fences), 12)
            self.assertEqual(len(fences) % 2, 0, "Unclosed code block")
            for suffix in ("scripts/install.sh", "scripts/install.ps1", "alva/examples/hello.alva"):
                self.assertIn("/" + VERSION + "/" + suffix, text)
            self.assertIn("docs/development-preview.md", text)
            self.assertIn("ALVA", text)
        for installer in ("scripts/install.sh", "scripts/install.ps1"):
            self.assertIn(VERSION, (ROOT / installer).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

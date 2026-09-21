import json
import pathlib
import re
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".codebuddy-plugin" / "plugin.json"
EXPECTED_SKILLS = {"bidding-management-core", "qingflow-bidding-builder", "qingflow-bidding-handoff"}


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.agent = (ROOT / cls.manifest["agents"][0]).read_text(encoding="utf-8")

    def test_manifest_contract(self):
        m = self.manifest
        self.assertEqual(m["name"], m["plugin"])
        self.assertEqual(m["name"], m["agentName"])
        self.assertEqual(m["version"], "1.0.0")
        self.assertEqual(m["expertType"], "agent")
        self.assertEqual(m["categoryId"], "12-IndustryConsultant")
        self.assertEqual(m["defaultInitPrompt"], m["quickPrompts"][0])
        self.assertEqual(len(m["tags"]), 3)
        self.assertEqual(len(m["quickPrompts"]), 3)
        self.assertEqual(len(m["skills"]), 3)
        self.assertEqual(m["dependencies"], {"connectors": ["qingflow"]})
        self.assertGreaterEqual(len(m["displayDescription"]["zh"]), 40)
        self.assertLessEqual(len(m["displayDescription"]["zh"]), 50)

    def test_skill_paths_and_frontmatter(self):
        names = set()
        for rel in self.manifest["skills"]:
            folder = ROOT / rel
            skill = folder / "SKILL.md"
            self.assertTrue(skill.is_file(), rel)
            text = skill.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            self.assertEqual(len(parts), 3, rel)
            front = parts[1]
            match = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", front)
            self.assertIsNotNone(match, rel)
            self.assertEqual(match.group(1), folder.name)
            names.add(folder.name)
        self.assertEqual(names, EXPECTED_SKILLS)

    def test_agent_frontmatter(self):
        front = self.agent.split("---", 2)[1]
        self.assertRegex(front, r"(?m)^description:\s*[A-Za-z]")
        self.assertNotIn("tools:", front)
        for skill in EXPECTED_SKILLS:
            self.assertIn("  - " + skill, front)

    def test_avatar(self):
        data = (ROOT / self.manifest["avatar"]).read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))
        self.assertLess(len(data), 500 * 1024)

    def test_package_hygiene(self):
        secret_patterns = (
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*['\"][^'\"]+"),
        )
        for path in ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            data = path.read_bytes()
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), str(path))
            if path.suffix.lower() in {".md", ".json", ".py"}:
                text = data.decode("utf-8")
                self.assertNotIn("[" + "TODO]", text)
                for pattern in secret_patterns:
                    self.assertIsNone(pattern.search(text), str(path))

    def test_external_links(self):
        allowed = {"https://qingflow.com/passport/login?utm_source=workbuddy"}
        found = set()
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".py"}:
                found.update(re.findall(r"https?://[^\s>)\"']+", path.read_text(encoding="utf-8")))
        self.assertEqual({url.rstrip("。.,") for url in found}, allowed)


if __name__ == "__main__":
    unittest.main(verbosity=2)

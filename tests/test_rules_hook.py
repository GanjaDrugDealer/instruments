"""Сквозные проверки pre-commit. Запуск: python -X utf8 tests/test_rules_hook.py."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class RulesHookTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "проект с пробелом"
        self.home = Path(temp.name) / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home),
                        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        for name in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE"):
            self.env.pop(name, None)
        for name in (".gitattributes", ".githooks/pre-commit", "scripts/rules-hook.py",
                     "scripts/compose-rules.py", "rules/CLAUDE.global.md"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, target)
        self.base = self.root / "rules/CLAUDE.global.md"
        self.base.write_bytes(b"a" * 8192)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.install()
        self.git("add", ".")
        self.commit()

    def command(self, *cmd, success=True):
        result = subprocess.run(cmd, cwd=self.root, env=self.env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=20)
        output = result.stdout.decode("utf-8", errors="replace")
        self.assertEqual(result.returncode == 0, success, output)
        return output

    def git(self, *args, success=True):
        return self.command("git", *args, success=success)

    def install(self):
        return self.command(sys.executable, "-X", "utf8", "scripts/rules-hook.py", "--install")

    def commit(self, *args, success=True):
        return self.git("commit", "-qm", "test", *args, success=success)

    def test_commit_uses_index(self):
        self.base.write_bytes(b"a" * 8193)
        self.git("add", "rules/CLAUDE.global.md")
        self.base.write_bytes(b"short")
        head = self.git("rev-parse", "HEAD")
        self.assertIn("8193", self.commit(success=False))
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.git("add", "rules/CLAUDE.global.md")
        self.base.write_bytes(b"a" * 8193)
        self.commit()
        self.assertEqual("short", self.git("show", "HEAD:rules/CLAUDE.global.md"))
        self.assertIn("8193", self.commit("-a", success=False))

    def test_assembly_profiles_and_unrelated_commit(self):
        profile = self.root / "rules/personal/second.md"
        profile.parent.mkdir()
        profile.write_bytes(b"p" * 4096)
        self.git("add", "rules/personal/second.md")
        output = self.commit(success=False)
        self.assertIn("second", output)
        self.assertIn("12 КиБ", output)
        profile.write_bytes(b"short")
        self.git("add", "rules/personal/second.md")
        self.commit()
        local = self.home / ".config/ai-rules/personal.md"
        local.parent.mkdir(parents=True)
        local.write_bytes(b"m" * 4096)
        self.base.write_bytes(b"b" * 8192)
        self.git("add", "rules/CLAUDE.global.md")
        self.assertIn("12 КиБ", self.commit(success=False))
        note = self.root / "note"
        note.touch()
        self.git("add", "note")
        self.assertNotIn("pre-commit:", self.commit("--only", "note"))
        self.assertIn("12 КиБ", self.commit(success=False))
        local.write_bytes(b"short")
        self.commit()

    def test_checkout_without_tracked_hook(self):
        (self.root / ".githooks/pre-commit").unlink()
        (self.root / "note").touch()
        self.git("add", "note")
        self.commit()
        self.base.write_bytes(b"new")
        self.git("add", "rules/CLAUDE.global.md")
        self.assertIn("missing .githooks/pre-commit", self.commit(success=False))

    def test_install_preserves_other_hooks(self):
        hook = self.root / ".git/hooks/pre-commit"
        installed = hook.read_bytes()
        self.install()
        self.assertEqual(hook.read_bytes(), installed)
        custom = b"#!/bin/sh\nexit 7\n"
        hook.write_bytes(custom)
        self.assertIn("сохранён", self.install())
        self.assertEqual(hook.read_bytes(), custom)
        self.git("config", "core.hooksPath", "custom-hooks")
        self.assertIn("используется", self.install())
        self.assertFalse((self.root / "custom-hooks").exists())


if __name__ == "__main__":
    unittest.main()

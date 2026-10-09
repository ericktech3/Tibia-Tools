import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".buildozer", "bin", "__pycache__"}


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(ROOT).parts)):
            yield p


class RepoHygieneTests(unittest.TestCase):
    def test_no_backup_or_wrapper_files_left(self):
        forbidden = []
        for pattern in ("*.bak", "*.orig"):
            forbidden.extend(ROOT.rglob(pattern))
        forbidden.extend(ROOT.glob("core/api.py"))
        forbidden.extend(ROOT.glob("core/bosses.py"))
        forbidden.extend(ROOT.glob("core/tibia.py"))
        junk_names = {"teste", "Teste", "Testa"}
        forbidden.extend(p for p in ROOT.rglob("*") if p.name in junk_names)
        self.assertEqual([], sorted({str(p.relative_to(ROOT)) for p in forbidden}))

    def test_no_logs_in_project(self):
        bad = [str(p.relative_to(ROOT)) for p in _files()
               if p.suffix == ".log" or p.name.endswith(".log.old")]
        self.assertEqual([], bad, "logs não devem ficar no projeto")

    def test_workflows_have_valid_extension(self):
        wf = ROOT / ".github" / "workflows"
        bad = [p.name for p in wf.iterdir() if p.suffix not in (".yml", ".yaml")] if wf.exists() else []
        self.assertEqual([], bad, "workflow com extensão estranha (backup?)")

    def test_gitignore_covers_generated_files(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for rule in ("__pycache__/", "*.py[cod]", "*.log"):
            self.assertIn(rule, text)

    def test_no_compiled_files_tracked_by_git(self):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=20)
        except Exception:
            self.skipTest("git indisponível")
        if out.returncode != 0:
            self.skipTest("não é um repositório git")
        bad = [l for l in out.stdout.splitlines()
               if l.endswith((".pyc", ".pyo", ".log")) or "__pycache__/" in l]
        self.assertEqual([], bad, "arquivos gerados estão versionados: git rm --cached")


if __name__ == "__main__":
    unittest.main()

"""Установка pre-commit в клоне _instruments и проверка правил из индекса Git."""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["rules/CLAUDE.global.md", ":(top,glob)rules/personal/*.md", "scripts/compose-rules.py"]
DISPATCH = b"""#!/bin/sh
if test -f .githooks/pre-commit; then
    exec sh .githooks/pre-commit "$@"
fi
# Older worktrees share the same hooks directory.
git diff --cached --quiet -- rules scripts/compose-rules.py && exit 0
echo 'pre-commit: missing .githooks/pre-commit for a rules change' >&2
exit 1
"""


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def install():
    if not (ROOT / ".git").exists():
        print("pre-commit: копия без .git, подключение не требуется.")
        return
    common = (ROOT / os.fsdecode(git("rev-parse", "--git-common-dir").rstrip(b"\r\n"))).resolve()
    hooks = (ROOT / os.fsdecode(git("rev-parse", "--git-path", "hooks").rstrip(b"\r\n"))).resolve()
    target = hooks / "pre-commit"
    if hooks == (ROOT / ".githooks").resolve():
        print("pre-commit: Git использует хук из репозитория.")
        return
    if hooks != (common / "hooks").resolve() or target.is_symlink():
        print(f"! pre-commit: используется {target}. Для своего хука см. README.")
        return
    hooks.mkdir(exist_ok=True)
    try:
        with target.open("xb") as out:
            out.write(DISPATCH)
    except FileExistsError:
        if target.read_bytes() != DISPATCH:
            print(f"! pre-commit: сохранён свой {target}. Подключение проверки описано в README.")
            return
    target.chmod(target.stat().st_mode | 0o111)
    print("pre-commit: проверка размера правил подключена.")


def check_index():
    # checkout-index использует в том числе временный индекс git commit -a / --only.
    names = git("ls-files", "--cached", "-z", "--", *INPUTS)
    with tempfile.TemporaryDirectory(prefix="instruments-index-") as tmp:
        snapshot = Path(tmp)
        subprocess.run(["git", "checkout-index", "--prefix", snapshot.as_posix() + "/",
                        "-z", "--stdin"], input=names, cwd=ROOT, check=True)
        checker = snapshot / "scripts" / "compose-rules.py"
        if not checker.is_file() or not (snapshot / "rules/CLAUDE.global.md").is_file():
            raise SystemExit("pre-commit: в индексе нужны базовые правила и scripts/compose-rules.py.")
        command = [sys.executable, "-X", "utf8", str(checker), "--check-size"]
        print("pre-commit: правила из индекса и дополнение текущей машины", flush=True)
        subprocess.run(command, check=True)

        # Чужой профиль проверяется без частного дополнения этой машины.
        empty_home = str(snapshot / "empty-home")
        clean_env = dict(os.environ, HOME=empty_home, USERPROFILE=empty_home)
        for profile in sorted((snapshot / "rules/personal").glob("*.md")):
            print(f"pre-commit: профиль {profile.stem}", flush=True)
            subprocess.run([*command, "--profile", profile.stem], env=clean_env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="подключить хук к этому клону")
    args = parser.parse_args()
    try:
        if args.install:
            install()
        else:
            check_index()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)

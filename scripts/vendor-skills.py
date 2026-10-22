#!/usr/bin/env python3
"""Сторонние скиллы по списку vendor-skills.txt -> skills/vendor/<агенты>/<имя>/.

  python3 -X utf8 scripts/vendor-skills.py            выложить ровно по закреплённым коммитам
  python3 -X utf8 scripts/vendor-skills.py --update   взять свежий коммит ветки по умолчанию и переписать список

Нужен только git. Качается лишь папка скилла (sparse + blob:none), символические ссылки
разворачиваются в файлы (для Windows). Если в папке скилла нет лицензии, рядом кладётся
LICENSE-UPSTREAM из корня репозитория. Папки в skills/vendor/, которых нет в списке, удаляются.
"""
import fnmatch, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LIST = HERE / "vendor-skills.txt"
VENDOR = HERE / "skills" / "vendor"
AGENTS = ("shared", "claude")
SHA = re.compile(r"^[0-9a-f]{40}$")


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def parse():
    entries = []
    for n, line in enumerate(LIST.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        f = line.split()
        if len(f) not in (5, 6) or f[0] not in AGENTS or (len(f) == 6 and not f[5].startswith("exclude=")):
            sys.exit(f"vendor-skills.txt:{n}: ожидается <агенты> <имя> <репо> <коммит> <путь> [exclude=…]")
        excl = f[5][len("exclude="):].split(",") if len(f) == 6 else []
        entries.append(dict(n=n, agent=f[0], name=f[1], repo=f[2], sha=f[3], path=f[4].strip("/"), excl=excl))
    names = [e["name"] for e in entries]
    dup = {x for x in names if names.count(x) > 1}
    if dup:
        sys.exit(f"повтор имён: {', '.join(sorted(dup))}")
    return entries


def fetch(repo, ref, paths, tmp):
    """Скачать нужные папки репозитория на коммите ref (или HEAD). Вернуть (каталог, полный sha)."""
    d = Path(tempfile.mkdtemp(dir=tmp))
    git("init", "-q", cwd=d)
    git("remote", "add", "origin", repo, cwd=d)
    git("sparse-checkout", "set", "--cone", *paths, cwd=d)  # cone: файлы корня (лицензия) + эти папки
    git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ref, cwd=d)
    git("checkout", "-q", "FETCH_HEAD", cwd=d)
    return d, git("rev-parse", "HEAD", cwd=d)


def place(src_root, e):
    src = src_root / e["path"]
    if not (src / "SKILL.md").is_file():
        sys.exit(f"{e['name']}: нет {e['path']}/SKILL.md в {e['repo']}")
    dst = VENDOR / e["agent"] / e["name"]
    if dst.exists():
        shutil.rmtree(dst)
    ignore = lambda d, names: [x for x in names if x == ".git" or any(
        fnmatch.fnmatch(str((Path(d) / x).relative_to(src)).replace("\\", "/"), p) for p in e["excl"])]
    shutil.copytree(src, dst, ignore=ignore)  # symlinks=False: ссылки копируются содержимым
    if not any(p.name.upper().startswith(("LICENSE", "LICENCE")) for p in dst.iterdir()):
        lic = next((p for p in sorted(src_root.iterdir()) if p.is_file() and p.name.upper().startswith(("LICENSE", "LICENCE"))), None)
        if lic:
            shutil.copy2(lic, dst / "LICENSE-UPSTREAM")


def main():
    update = "--update" in sys.argv[1:]
    entries = parse()
    lines = LIST.read_text(encoding="utf-8").splitlines(keepends=True)
    groups = {}
    for e in entries:
        if not update and not SHA.match(e["sha"]):
            sys.exit(f"vendor-skills.txt:{e['n']}: коммит должен быть полным sha (40 знаков) — запустите с --update")
        groups.setdefault((e["repo"], "HEAD" if update else e["sha"]), []).append(e)
    with tempfile.TemporaryDirectory() as tmp:
        for (repo, ref), es in groups.items():
            root, sha = fetch(repo, ref, [e["path"] for e in es], tmp)
            for e in es:
                place(root, e)
                if sha != e["sha"]:
                    lines[e["n"] - 1] = lines[e["n"] - 1].replace(e["sha"], sha, 1)
                print(f"  {e['agent']}/{e['name']} @ {sha[:7]}")
    keep = {(e["agent"], e["name"]) for e in entries}
    for agent in AGENTS:
        for d in sorted((VENDOR / agent).glob("*")) if (VENDOR / agent).is_dir() else []:
            if d.is_dir() and (agent, d.name) not in keep:
                shutil.rmtree(d)
                print(f"  удалён {agent}/{d.name} (нет в списке)")
    if update:
        LIST.write_text("".join(lines), encoding="utf-8", newline="\n")
        print("Список обновлён — просмотреть git diff.")
    print("Готово. Разложить по агентам: install.sh / install.ps1.")


if __name__ == "__main__":
    main()

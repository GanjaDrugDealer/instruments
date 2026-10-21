"""agy.py — вызов Antigravity CLI (agy) по подписке из кода: квота, текст по схеме, картинка. Только stdlib.

Скопировать в scripts/ проекта (не ссылаться). Скилл antigravity, справка — references/stream-json.md.

    python agy.py usage [--model M]          — остаток квоты группы модели (Gemini / Claude and GPT), JSON
    python agy.py text  < задача.json        — один вызов «вход → JSON по схеме», JSON
        задача: {"prompt": "...", "schema": {...}|"строка"|"путь", "model": "gemini-3.8-flash-medium",
                 "effort": "medium", "timeout_s": 300, "min_pct": 25, "name": "метка для журнала"}
    python agy.py image <файл.jpg> [--ref лого.png] < промпт   — одна картинка, JSON

Общие ключи (или переменные окружения):
    --agy      AGY_CMD    чем запускать agy: путь к agy или к обёртке (/usr/local/bin/agy-<имя>),
                          либо JSON-список ["python", "fake_agy.py"]. По умолчанию — agy из PATH,
                          ~/.local/bin/agy, %LOCALAPPDATA%\\agy\\bin\\agy.exe
    --home     AGY_HOME   домашняя папка пользователя, от которого работает agy (там .gemini/antigravity-cli/brain);
                          по умолчанию ~. На сервере с обёрткой — /home/<пользователь agy>
    --workdir  AGY_WORKDIR рабочая папка agy (доверенная, settings.json → trustedWorkspaces); сюда кладётся
                          образец для картинки. По умолчанию <home>/work, если есть, иначе текущая
    --state    AGY_STATE  папка помощника: блокировки квоты, кэш /usage, журнал. По умолчанию ~/.cache/agy-helper
    --lock     AGY_LOCK   файл-замок «один вызов agy за раз»; общий у всех помощников одного аккаунта
                          (на сервере — тот же, что у уже стоящего помощника). По умолчанию <state>/agy.lock
    --expect-ip AGY_EXPECT_IP  постоянный адрес выхода аккаунта; на ПК — agy не зовётся, пока VPN не даёт этот
                          адрес (правило «один адрес на аккаунт»). На сервере с обёрткой-туннелем не задавать:
                          помощник сам ходит в сеть напрямую, адрес проверяет ufw и обёртка

Коды выхода: 0 — готово; 1 — ошибка agy; 2 — неверный вызов; 3 — занято (другой вызов > 10 мин);
4 — квота (сторож бюджета или блок после 429), в ответе "until"; 5 — картинки шли дольше wait_s
(по умолчанию 3600 с), текст так и не выполнен.

Картинки — приоритет (решение пользователя 21.10): картинка, ждущая замка, останавливает идущий текстовый вызов
этого аккаунта, а новые тексты не встают в очередь, пока она ждёт. Остановленный текст ждёт конца картинок и
запускается заново сам (с начала: agy не продолжает прерванный ответ), в ответе "preempted": N.
AGY_YIELD_TO — шаблон pgrep -f для чужого
помощника картинок, которому текст тоже уступает (на сервере smm — «smm-agy-image gen»).
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time

ISO = "%Y-%m-%dT%H:%M:%SZ"
EXHAUSTED_RX = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|exhausted your capacity|rate limit", re.I)


def iso(t):
    return time.strftime(ISO, time.gmtime(t))


def from_iso(s):
    try:
        import calendar
        return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return 0


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False))
    sys.exit(code)


# ---------- настройка ----------

def agy_cmd(value):
    value = value or os.environ.get("AGY_CMD", "")
    if value.startswith("["):
        return json.loads(value)
    if value:
        return [value]
    for c in (shutil.which("agy"), os.path.expanduser("~/.local/bin/agy"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe")):
        if c and os.path.isfile(c):
            return [c]
    out({"ok": False, "error": "agy не найден: поставьте официальным установщиком или укажите --agy"}, 2)


class Cfg:
    def __init__(self, a):
        self.agy = agy_cmd(a.agy)
        self.home = os.path.expanduser(a.home or os.environ.get("AGY_HOME") or "~")
        wd = a.workdir or os.environ.get("AGY_WORKDIR") or os.path.join(self.home, "work")
        self.workdir = wd if os.path.isdir(wd) else os.getcwd()
        self.state = os.path.expanduser(a.state or os.environ.get("AGY_STATE") or "~/.cache/agy-helper")
        os.makedirs(self.state, exist_ok=True)
        self.lock = a.lock or os.environ.get("AGY_LOCK") or self.path("agy.lock")
        self.brain = os.path.join(self.home, ".gemini", "antigravity-cli", "brain")
        self.expect_ip = a.expect_ip or os.environ.get("AGY_EXPECT_IP", "")

    def path(self, name):
        return os.path.join(self.state, name)

    def check_exit(self):
        if not self.expect_ip:
            return
        import urllib.request
        try:
            ip = urllib.request.urlopen("https://ipinfo.io/ip", timeout=10).read().decode().strip()
        except OSError as e:
            out({"ok": False, "error": f"не узнать адрес выхода ({e}) — agy не зову"}, 2)
        if ip != self.expect_ip:
            out({"ok": False, "error": f"выход {ip}, а у аккаунта {self.expect_ip} — включите VPN на этот адрес"}, 2)
        self.expect_ip = ""   # раз за запуск

    def run(self, args, timeout, stdin=None):
        self.check_exit()
        # cwd — доверенная папка (settings.json → trustedWorkspaces): там agy видит образец картинки
        return subprocess.run(self.agy + args, input=stdin, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=self.workdir)

    def run_yielding(self, args, timeout, stdin):
        """Как run, но уступает картинке: ждёт картинка — agy останавливается, ответ preempted (повторить позже)."""
        self.check_exit()
        p = subprocess.Popen(self.agy + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace", cwd=self.workdir,
                             start_new_session=os.name != "nt")
        t0, outs, first = time.time(), None, stdin
        while outs is None:
            try:
                outs = p.communicate(input=first, timeout=2)   # вход отдаётся один раз, дальше — только ждём
            except subprocess.TimeoutExpired:
                first = None
                if time.time() - t0 > timeout or image_waiting(self.lock):
                    try:   # вся группа: agy запускает свои процессы (обёртка, sudo, субагенты)
                        os.killpg(p.pid, 15) if os.name != "nt" else p.terminate()
                    except OSError:
                        pass
                    p.communicate()
                    if time.time() - t0 > timeout:
                        raise subprocess.TimeoutExpired(args, timeout)
                    return None
        return subprocess.CompletedProcess(args, p.returncode, outs[0], outs[1])

    def journal(self, rec):
        try:
            with open(self.path("journal.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": iso(time.time()), **rec}, ensure_ascii=False) + "\n")
        except OSError:
            pass


# ---------- одна задача за раз ----------

def image_waiting(lock):
    """Картинка — приоритет (решение пользователя 21.10): ждёт ли картинка очереди. Своя — флаг <замок>.image-wait,
    который ждущая картинка обновляет каждые 2 с; чужая (на сервере — smm-agy-image) — по процессу из AGY_YIELD_TO
    (шаблон для pgrep -f, например «smm-agy-image gen»)."""
    try:
        if time.time() - os.path.getmtime(lock + ".image-wait") < 30:
            return True
    except OSError:
        pass
    pat = os.environ.get("AGY_YIELD_TO", "")
    if pat and os.name != "nt":
        return subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0
    return False


class Lock:
    """Замок на файл: два вызова agy одного аккаунта одновременно не идут (квота, память, разговоры в brain).
    Картинка, пока ждёт, держит флаг image-wait; текст не встаёт в очередь, пока ждёт картинка."""

    def __init__(self, path, kind, wait=600):
        self.f, flag = open(path, "a+"), path + ".image-wait"
        t0 = time.time()
        while True:
            if kind == "image":   # время — явно: на Windows пустой файл при перезаписи его не меняет
                with open(flag, "w") as f:
                    f.write(str(os.getpid()))
                os.utime(flag)
            if (kind == "image" or not image_waiting(path)) and self._try():
                break
            if time.time() - t0 > wait:
                out({"ok": False, "error": f"занято: другой вызов agy идёт дольше {wait} с"}, 3)
            time.sleep(2)
        if kind == "image":
            try:
                os.remove(flag)
            except OSError:
                pass

    def release(self):
        self.f.close()   # закрытие снимает замок и flock, и msvcrt

    def _try(self):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


# ---------- квота ----------

def parse_usage(text, model=""):
    """Строки agy /usage: «Gemini Models<TAB>Weekly Limit Remaining<TAB>69%<TAB>2026-10-26T18:35:26Z».
    Группа по модели: claude-*/gpt-* — «Claude and GPT models», остальное — «Gemini Models».
    У Starter строки «Five Hour» нет — тогда five_hour_pct = None."""
    group = "Claude and GPT" if re.match(r"(claude|gpt)", model or "", re.I) else "Gemini"
    res = {"group": group}
    for key, label in (("weekly", "Weekly"), ("five_hour", "Five Hour")):
        m = re.search(rf"^\s*{group}[^\n]*?{label} Limit Remaining[\t ]+(\d+(?:\.\d+)?)%[\t ]*(\S*)", text, re.M | re.I)
        res[f"{key}_pct"] = float(m.group(1)) if m else None
        res[f"{key}_reset"] = (m.group(2) or None) if m else None
    return res


def usage(cfg, model="", max_age=600):
    """Квота с кэшем 10 мин (сам /usage бесплатный, но это ещё один запуск agy ~5–40 с)."""
    cache = cfg.path("usage_cache.json")
    try:
        d = json.load(open(cache, encoding="utf-8"))
        if time.time() - d["time"] < max_age:
            return parse_usage(d["raw"], model), d["raw"]
    except (OSError, ValueError, KeyError):
        pass
    try:
        r = cfg.run(["-p", "/usage", "--print-timeout", "45s"], timeout=60)
        raw = r.stdout or r.stderr or ""
    except subprocess.TimeoutExpired:
        raw = "agy /usage: таймаут 60 с"
    if "Limit Remaining" in raw:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "raw": raw}, f)
    return parse_usage(raw, model), raw


def budget_ok(u, min_pct):
    for key, what in (("weekly_pct", "недели"), ("five_hour_pct", "окна 5 ч")):
        if u.get(key) is not None and u[key] < min_pct:
            return False, f"остаток {what} {u[key]}% < {min_pct}%"
    if u.get("weekly_pct") is None and u.get("five_hour_pct") is None:
        return False, "нет данных о квоте в /usage (вход слетел? agy не ответил?)"
    return True, ""


def blocked(cfg, kind):
    try:
        until = float(json.load(open(cfg.path(f"block_{kind}.json"), encoding="utf-8"))["until"])
        return until if until > time.time() else 0
    except (OSError, ValueError, KeyError):
        return 0


def block(cfg, kind, until, reason):
    with open(cfg.path(f"block_{kind}.json"), "w", encoding="utf-8") as f:
        json.dump({"until": until, "until_iso": iso(until), "at": iso(time.time()), "reason": reason[:300]}, f,
                  ensure_ascii=False)


def reset_after(text):
    """«reset after ~3 hours» / «reset after 4h29m54s» → секунды (0 — не нашли)."""
    m = re.search(r"reset after ~?(?:(\d+(?:\.\d+)?) ?hours?|(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?)", text)
    if not m:
        return 0
    if m.group(1):
        return float(m.group(1)) * 3600
    return sum(int(g or 0) * k for g, k in zip(m.group(2, 3, 4), (3600, 60, 1)))


# ---------- текст по схеме ----------

def parse_stream(stdout):
    """Вывод agy --output-format stream-json: по строке JSON на событие. Ответ — в последней строке
    {"event":"result","result":{status, response|structured_output, usage, num_turns}}. Инструменты —
    {"event":"step_update","step_update":{"step_type":"tool","tool_name":...}}; finish — не инструмент."""
    result, finish, tools, tail = None, None, False, []
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        su = e.get("step_update") or {}
        if e.get("event") != "user_input" and su.get("step_type") != "user_input":
            tail = (tail + [e])[-5:]
        if e.get("event") == "step_update":
            info = su.get("tool_info") or {}
            name = su.get("tool_name") or info.get("name")
            if su.get("step_type") == "tool" and name != "finish":
                tools = True
            elif info.get("parameters") and (name == "finish" or su.get("step_type") == "finish"):
                finish = info["parameters"]
        if e.get("event") == "result":
            result = e.get("result") or e   # в 1.4.2 result вложен; на всякий случай — и плоский
    if result is None:
        return {"ok": False, "error": "в выводе agy нет строки event=result", "tools_used": tools, "stream_tail": tail}
    resp = result.get("structured_output") or result.get("response") or finish
    if isinstance(resp, str):
        s = resp.strip()
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
        try:
            resp = json.loads(s)
        except ValueError:
            resp = s or None
    turns = result.get("num_turns", 1)
    r = {"ok": result.get("status") == "SUCCESS" and bool(resp), "status": result.get("status"), "response": resp,
         "usage": result.get("usage") or {}, "num_turns": turns, "tools_used": tools or turns > 1,
         "error": result.get("error")}
    if not resp:
        r.update(ok=False, error=r["error"] or "пустой ответ модели", stream_tail=tail)
    return r


def cmd_text(cfg, task):
    prompt = task.get("prompt") or ""
    if not prompt:
        out({"ok": False, "error": "пустой prompt"}, 2)
    model = task.get("model", "gemini-3.8-flash-medium")
    effort = task.get("effort", "medium")
    timeout = max(60, min(900, int(task.get("timeout_s", 300))))
    name = task.get("name", "text")
    until = blocked(cfg, "text")
    if until:
        out({"ok": False, "blocked": True, "until": iso(until), "error": f"квота текста: блок до {iso(until)}"}, 4)
    u, _ = usage(cfg, model)
    ok, why = budget_ok(u, float(task.get("min_pct", 25)))
    if not ok:
        out({"ok": False, "budget": True, "usage": u, "error": f"сторож бюджета: {why}"}, 4)
    args = ["-p=", "--input-format", "stream-json", "--output-format", "stream-json",
            "--model", model, "--effort", effort, "--print-timeout", f"{timeout - 20}s"]
    schema = task.get("schema")
    if schema:
        # путь agy может не увидеть (работает от другого пользователя) — передаём саму схему строкой
        if isinstance(schema, str) and os.path.isfile(schema):
            schema = open(schema, encoding="utf-8").read()
        args += ["--json-schema", schema if isinstance(schema, str) else json.dumps(schema, ensure_ascii=False)]
    line = json.dumps({"event": "user", "message": {"content": prompt}}, ensure_ascii=False) + "\n"
    # картинка — приоритет: остановленный ради неё вызов ждёт, пока картинки дорисуются, и идёт заново сам
    deadline, preempted = time.time() + int(task.get("wait_s", 3600)), 0
    while True:
        lock = Lock(cfg.lock, "text", wait=max(60, deadline - time.time()))   # ссылку держать: иначе замок снят
        t0 = time.time()
        try:
            r = cfg.run_yielding(args, timeout=timeout, stdin=line)
        except subprocess.TimeoutExpired:
            cfg.journal({"kind": "text", "name": name, "model": model, "status": "TIMEOUT", "sec": round(time.time() - t0)})
            out({"ok": False, "error": f"agy: таймаут {timeout} с"}, 1)
        if r is not None:
            break
        lock.release()
        preempted += 1
        cfg.journal({"kind": "text", "name": name, "model": model, "status": "PREEMPTED", "sec": round(time.time() - t0)})
        if time.time() > deadline:
            out({"ok": False, "preempted": preempted,
                 "error": "картинки идут дольше wait_s — текст не выполнен, повторить позже"}, 5)
        time.sleep(3)   # картинка забирает замок; текст встанет в очередь после неё
    res = parse_stream(r.stdout)
    res["seconds"] = round(time.time() - t0)
    if preempted:
        res["preempted"] = preempted   # сколько раз уступил картинке и начинал заново
    # 429 ищем только в ошибках: в тексте ответа и счётчиках токенов «429» бывает само по себе (14290 токенов)
    err = (r.stderr or "") + "\n" + str(res.get("error") or "")
    if not res["ok"] and EXHAUSTED_RX.search(err):
        # сброс — из /usage, если там уже почти ноль; иначе из текста ошибки; иначе на 6 ч
        resets = [u.get(f"{k}_reset") for k in ("five_hour", "weekly") if (u.get(f"{k}_pct") or 100) < 5]
        until = max([from_iso(x) for x in resets if x] + [0])
        until = until if until > time.time() else time.time() + (reset_after(err) or 6 * 3600)
        block(cfg, "text", until, err.strip()[-300:])
        res.update(blocked=True, until=iso(until))
    if not res["ok"] and not res.get("error"):
        res["error"] = (r.stderr or "").strip().splitlines()[-1:] or [f"код {r.returncode}"]
    cfg.journal({"kind": "text", "name": name, "model": model, "effort": effort, "status": res.get("status"),
                 "ok": res["ok"], "sec": res["seconds"], "usage": res.get("usage"), "tools_used": res.get("tools_used"),
                 "weekly_before": u.get("weekly_pct"), "error": str(res.get("error") or "")[:200] or None})
    out(res, 0 if res["ok"] else (4 if res.get("blocked") else 1))


# ---------- картинка ----------

IMAGE_MODEL = ["--model", "gemini-3.8-flash-low", "--effort", "low"]   # меньше рассуждений — меньше расход


def cmd_image(cfg, dst, ref):
    prompt = sys.stdin.read(8000).strip()
    if not prompt:
        out({"ok": False, "error": "пустой промпт"}, 2)
    until = blocked(cfg, "image")
    if until:
        out({"ok": False, "exhausted": True, "until": iso(until), "error": f"квота картинок: блок до {iso(until)}"}, 4)
    lock = Lock(cfg.lock, "image")   # держать ссылку до выхода
    if ref:
        # генератор берёт входную картинку только файлом из рабочей папки agy
        if not os.path.isfile(ref):
            out({"ok": False, "error": f"нет образца {ref}"}, 2)
        local = os.path.join(cfg.workdir, os.path.basename(ref))
        if os.path.abspath(local) != os.path.abspath(ref):
            shutil.copyfile(ref, local)
        prompt += (f"\nPass the file {local} to the image generation tool as an input image "
                   "(it is the attached logo); do not modify the logo.")
    t0 = time.time()
    try:
        r = cfg.run(["-p", prompt] + IMAGE_MODEL + ["--output-format", "json", "--print-timeout", "280s"], timeout=300)
    except subprocess.TimeoutExpired:
        out({"ok": False, "error": "agy: таймаут 300 с", "sec": round(time.time() - t0)}, 1)
    try:
        js = json.loads(r.stdout)
    except ValueError:
        js = {}
    conv = js.get("conversation_id", "")
    files = []
    if re.fullmatch(r"[0-9a-f-]{36}", conv or ""):
        files = sorted((f for e in ("jpg", "jpeg", "png", "webp") for f in glob.glob(os.path.join(cfg.brain, conv, f"*.{e}"))),
                       key=os.path.getmtime)
    if files:
        ext = files[-1].rsplit(".", 1)[1].replace("jpeg", "jpg")
        dst = dst if dst.lower().endswith("." + ext) else os.path.splitext(dst)[0] + "." + ext
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.copyfile(files[-1], dst)
        res = {"ok": True, "file": dst, "sec": round(time.time() - t0), "conversation": conv,
               "tokens": (js.get("usage") or {}).get("total_tokens")}
        cfg.journal({"kind": "image", **res})
        out(res)
    # 429 генератора виден только в журнале разговора субагента: brain/<разговор>/.system_generated/logs/transcript.jsonl
    for t in glob.glob(os.path.join(cfg.brain, "*", ".system_generated", "logs", "transcript.jsonl")):
        try:
            if os.path.getmtime(t) < t0:
                continue
            txt = open(t, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "RESOURCE_EXHAUSTED" in txt:
            until = time.time() + (reset_after(txt) or 24 * 3600)
            block(cfg, "image", until, "RESOURCE_EXHAUSTED у генератора картинок")
            cfg.journal({"kind": "image", "ok": False, "exhausted": True, "until": iso(until)})
            out({"ok": False, "exhausted": True, "until": iso(until), "sec": round(time.time() - t0),
                 "error": f"квота картинок исчерпана, сброс {iso(until)}"}, 4)
    err = (r.stderr or "").strip().splitlines()[-1:] or [str(js.get("status", ""))]
    cfg.journal({"kind": "image", "ok": False, "rc": r.returncode, "error": err[0][:200]})
    out({"ok": False, "rc": r.returncode, "sec": round(time.time() - t0),
         "error": f"нет картинки: {err[0][:300]} | ответ: {str(js.get('response', ''))[:200]}"}, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("agy", "home", "workdir", "state", "lock"):
        ap.add_argument(f"--{k}")
    ap.add_argument("--expect-ip", dest="expect_ip")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("usage")
    s.add_argument("--model", default="")
    s.add_argument("--fresh", action="store_true", help="не брать кэш")
    sub.add_parser("text")
    s = sub.add_parser("image")
    s.add_argument("dst")
    s.add_argument("--ref")
    a = ap.parse_args()
    cfg = Cfg(a)
    if a.cmd == "usage":
        u, raw = usage(cfg, a.model, max_age=0 if a.fresh else 600)
        u["blocked_text"] = iso(blocked(cfg, "text")) if blocked(cfg, "text") else None
        u["blocked_image"] = iso(blocked(cfg, "image")) if blocked(cfg, "image") else None
        out({"ok": u["weekly_pct"] is not None or u["five_hour_pct"] is not None, **u, "raw": raw.strip()[:2000]})
    if a.cmd == "text":
        try:
            task = json.loads(sys.stdin.read())
        except ValueError as e:
            out({"ok": False, "error": f"на stdin не JSON: {e}"}, 2)
        cmd_text(cfg, task)
    cmd_image(cfg, a.dst, a.ref)


if __name__ == "__main__":
    main()

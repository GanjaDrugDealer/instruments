"""Проверка agy.py без сети и без настоящего agy: поддельный agy отдаёт записанные с сервера ответы (agy 1.4.2).

    python -X utf8 test_agy.py
"""
import json, os, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
AGY_PY = HERE / "agy.py"

# поддельный agy: режим — из FAKE_AGY_MODE, дом — из FAKE_AGY_HOME
FAKE = r'''
import json, os, sys, uuid, pathlib
mode, home = os.environ.get("FAKE_AGY_MODE", "ok"), pathlib.Path(os.environ["FAKE_AGY_HOME"])
a = sys.argv[1:]
if a[:2] == ["-p", "/usage"]:
    if mode == "starter":
        print("Gemini Models\tWeekly Limit Remaining\t69%\t2026-10-26T12:28:06Z")
    elif mode == "low":
        print("Gemini Models\tWeekly Limit Remaining\t87%\t2026-10-26T18:35:26Z")
        print("Gemini Models\tFive Hour Limit Remaining\t3%\t2099-10-20T18:40:09Z")
    else:
        print("Gemini Models\tWeekly Limit Remaining\t87%\t2026-10-26T18:35:26Z")
        print("Gemini Models\tFive Hour Limit Remaining\t91%\t2026-10-20T18:40:09Z")
        print("Claude and GPT models\tWeekly Limit Remaining\t40%\t2026-10-26T20:03:51Z")
        print("Claude and GPT models\tFive Hour Limit Remaining\t20%\t2026-10-20T21:09:55Z")
    sys.exit(0)
if a and a[0] == "-p=":
    msg = json.loads(sys.stdin.readline())
    assert msg["event"] == "user" and msg["message"]["content"]
    print(json.dumps({"event": "user_input", "x": 1}))
    if mode == "slow" and not (home / "slow-done").exists():   # «думает» 30 с только в первый раз
        import time
        (home / "slow-done").write_text("1")
        time.sleep(30)
    if mode == "tools_empty":
        print(json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "tool_name": "list_dir"}}))
        print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "", "num_turns": 2, "usage": {}}}))
    elif mode == "finish":
        print(json.dumps({"event": "step_update", "step_update": {"step_type": "tool", "tool_name": "finish",
                          "tool_info": {"parameters": {"verdict": "ok"}}}}))
        print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "", "num_turns": 1, "usage": {}}}))
    elif mode == "429":
        print("Error: 429 RESOURCE_EXHAUSTED, reset after 4h29m54s", file=sys.stderr)
        print(json.dumps({"event": "result", "result": {"status": "ERROR", "response": "", "error": "429"}}))
        sys.exit(1)
    else:   # 14290 токенов: «429» внутри числа не должен ставить блок
        print(json.dumps({"event": "result", "result": {"conversation_id": "x", "status": "SUCCESS",
              "response": "{\"claims\": [1, 2]}", "num_turns": 1,
              "usage": {"input_tokens": 14290, "output_tokens": 429, "thinking_tokens": 0}}}))
    sys.exit(0)
if a and a[0] == "-p":
    conv = str(uuid.uuid4())
    d = home / ".gemini" / "antigravity-cli" / "brain" / conv
    d.mkdir(parents=True)
    if mode == "img_exhausted":
        sub = home / ".gemini" / "antigravity-cli" / "brain" / str(uuid.uuid4()) / ".system_generated" / "logs"
        sub.mkdir(parents=True)
        (sub / "transcript.jsonl").write_text('{"error":"RESOURCE_EXHAUSTED ... reset after ~2 hours"}')
    else:
        (d / "image_1.jpeg").write_bytes(b"\xff\xd8fake")
    print(json.dumps({"conversation_id": conv, "status": "SUCCESS", "response": "done", "usage": {"total_tokens": 5000}}))
    sys.exit(0)
sys.exit(9)
'''

fails = 0


def check(cond, what):
    global fails
    print(("  ok  " if cond else "  FAIL ") + what)
    fails += not cond


def env_for(tmp, mode, state):
    return {**os.environ, "FAKE_AGY_MODE": mode, "FAKE_AGY_HOME": str(tmp / "home"),
            "AGY_CMD": json.dumps([sys.executable, str(tmp / "fake_agy.py")]), "AGY_HOME": str(tmp / "home"),
            "AGY_STATE": str(tmp / (state or "state-" + mode)), "AGY_WORKDIR": str(tmp / "home" / "work")}


def parse(code, stdout, stderr=""):
    try:
        return code, json.loads(stdout)
    except ValueError:
        return code, {"raw": stdout, "stderr": stderr}


def run(tmp, mode, args, stdin="", state=None):
    r = subprocess.run([sys.executable, "-X", "utf8", str(AGY_PY)] + args, input=stdin, capture_output=True,
                       text=True, encoding="utf-8", env=env_for(tmp, mode, state))
    return parse(r.returncode, r.stdout, r.stderr)


def main():
    sys.path.insert(0, str(HERE))
    import agy
    print("--- разбор /usage и сброса ---")
    pro = ("Gemini Models\tWeekly Limit Remaining\t87%\t2026-10-26T18:35:26Z\n"
           "Gemini Models\tFive Hour Limit Remaining\t91%\t2026-10-20T18:40:09Z\n"
           "Claude and GPT models\tWeekly Limit Remaining\t98%\t2026-10-26T20:03:51Z\n")
    u = agy.parse_usage(pro, "gemini-3.8-flash-high")
    check(u["weekly_pct"] == 87 and u["five_hour_pct"] == 91, f"Pro, Gemini: {u}")
    u = agy.parse_usage(pro, "claude-sonnet-4-6")
    check(u["weekly_pct"] == 98 and u["five_hour_pct"] is None, f"Claude — своя группа: {u}")
    check(agy.reset_after("reset after 4h29m54s") == 4 * 3600 + 29 * 60 + 54, "сброс 4h29m54s")
    check(agy.reset_after("reset after ~3 hours") == 3 * 3600, "сброс ~3 hours")

    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        (tmp / "fake_agy.py").write_text(FAKE, encoding="utf-8")
        (tmp / "home" / "work").mkdir(parents=True)
        task = json.dumps({"prompt": "Проверь", "schema": {"type": "object"}, "name": "t"})

        print("--- текст ---")
        code, r = run(tmp, "ok", ["text"], task)
        check(code == 0 and r.get("response") == {"claims": [1, 2]} and not r.get("blocked"),
              f"ответ по схеме разобран, «14290» не 429: {r}")
        code, r = run(tmp, "tools_empty", ["text"], task)
        check(code == 1 and r.get("tools_used") and r.get("stream_tail"), "полез в инструменты и ответил пусто — ошибка с хвостом")
        code, r = run(tmp, "finish", ["text"], task)
        check(code == 0 and r.get("response") == {"verdict": "ok"}, "пустой response — ответ из параметров finish")
        code, r = run(tmp, "429", ["text"], task)
        check(code == 4 and r.get("blocked"), f"429 → блок текста: {r.get('until')}")
        code, r = run(tmp, "429", ["text"], task)
        check(code == 4 and "блок до" in r.get("error", ""), "пока блок — agy не зовётся")
        code, r = run(tmp, "low", ["text"], task)
        check(code == 4 and r.get("budget"), "окно 5 ч < 25 % — сторож бюджета")
        code, r = run(tmp, "ok", ["text"], json.dumps({"prompt": "x", "model": "claude-sonnet-4-6", "min_pct": 25}))
        check(code == 4 and r.get("budget"), "Claude: окно 5 ч 20 % < 25 % — сторож по своей группе")
        code, r = run(tmp, "starter", ["usage"])
        check(code == 0 and r["weekly_pct"] == 69 and r["five_hour_pct"] is None, "Starter: строки «Five Hour» нет")

        os.environ["AGY_EXPECT_IP"] = "192.0.2.1"   # адрес из документации: чужой выход (или нет сети) — код 2
        code, r = run(tmp, "ok-ip", ["text"], task)
        del os.environ["AGY_EXPECT_IP"]
        check(code == 2 and "agy" not in r.get("raw", "") and not r.get("ok"), f"чужой адрес выхода — agy не зовётся: {r.get('error')}")

        print("--- картинка ---")
        ref = tmp / "logo.png"
        ref.write_bytes(b"png")
        code, r = run(tmp, "ok", ["image", str(tmp / "out" / "pic.jpg"), "--ref", str(ref)], "Нарисуй кота")
        check(code == 0 and pathlib.Path(r.get("file", "")).is_file() and (tmp / "home" / "work" / "logo.png").is_file(),
              f"картинка из brain/<разговор>, образец — в рабочей папке: {r.get('file')}")
        code, r = run(tmp, "img_exhausted", ["image", str(tmp / "out" / "pic2.jpg")], "Нарисуй кота")
        check(code == 4 and r.get("exhausted"), f"RESOURCE_EXHAUSTED в разговоре субагента → блок картинок до {r.get('until')}")
        code, r = run(tmp, "img_exhausted", ["image", str(tmp / "out" / "pic3.jpg")], "Нарисуй кота")
        check(code == 4 and "блок до" in r.get("error", ""), "пока блок картинок — agy не зовётся")

        print("--- картинка — приоритет ---")
        import time
        t0 = time.time()
        slow = subprocess.Popen([sys.executable, "-X", "utf8", str(AGY_PY), "text"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, encoding="utf-8", env=env_for(tmp, "slow", "shared"))
        slow.stdin.write(task)
        slow.stdin.close()
        time.sleep(4)   # текст взял замок и «думает» 30 с
        code, r = run(tmp, "ok", ["image", str(tmp / "out" / "pic4.jpg")], "Нарисуй кота", state="shared")
        t_img = time.time() - t0
        tcode, tr = parse(slow.wait(60), slow.stdout.read())
        check(code == 0 and r.get("ok") and t_img < 20, f"картинка прошла, не дожидаясь текста ({t_img:.0f} с из 30)")
        check(tcode == 0 and tr.get("preempted") == 1 and tr.get("response") == {"claims": [1, 2]},
              f"текст уступил картинке и сам доделан после неё: preempted={tr.get('preempted')}, "
              f"всего {time.time() - t0:.0f} с")

    print("ИТОГ:", "всё зелёное" if not fails else f"провалов: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

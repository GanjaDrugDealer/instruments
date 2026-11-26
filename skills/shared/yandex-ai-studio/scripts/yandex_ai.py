"""Local IAM auth and DeepSeek requests for a Yandex AI Studio subscription."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


RESPONSES_URL = "https://apps.ai.api.cloud.yandex.net/v1/responses"
MODEL = "deepseek-v4.1-flash"
PORTABLE_DIR = (Path(__file__).resolve().parent / "../../../../bin/yandex-cloud").resolve()


class YandexAIError(RuntimeError):
    """An error safe to display without disclosing credentials."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def find_yc(executable=None):
    if executable is not None:
        resolved = shutil.which(os.path.expanduser(os.fspath(executable)))
    else:
        name = "yc.exe" if os.name == "nt" else "yc"
        resolved = shutil.which(name) or shutil.which(str(PORTABLE_DIR / name))
    if not resolved:
        raise YandexAIError("Не найден yc. Укажи путь к CLI через --yc.")
    return str(Path(resolved).resolve())


def yc_command(args, *, executable=None, profile=None):
    binary = Path(find_yc(executable))
    command = [str(binary), *args]
    if profile:
        command.extend(["--profile", profile])
    env = None
    if os.name == "nt" and binary.parent == PORTABLE_DIR:
        private_profile = PORTABLE_DIR / "profile"
        use_private_profile = private_profile.is_dir()
        temp = (private_profile if use_private_profile else PORTABLE_DIR) / "tmp"
        try:
            temp.mkdir(exist_ok=True)
        except OSError:
            raise YandexAIError("Не удалось создать временную папку рядом с портативным yc.") from None
        env = dict(os.environ, TEMP=str(temp), TMP=str(temp))
        if use_private_profile:
            env["USERPROFILE"] = str(private_profile)
    return command, env


def yc_read(args, *, executable=None, profile=None):
    command, env = yc_command((*args, "--no-browser"), executable=executable, profile=profile)
    try:
        result = subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
    except subprocess.TimeoutExpired:
        raise YandexAIError("YC CLI не ответил за 25 секунд. Проверь сеть и вход.") from None
    except OSError:
        raise YandexAIError("Не удалось запустить YC CLI.") from None
    if result.returncode:
        if "yc_logs" in result.stderr and "mkdir" in result.stderr:
            raise YandexAIError("YC CLI не может записать журналы в текущий временный каталог.")
        raise YandexAIError(
            "YC CLI вернул ошибку. Проверь профиль через yc config profile list "
            "и при необходимости запусти подкоманду init этого скрипта в своём терминале."
        )
    return result.stdout.strip()


def windows_login_url(pid):
    netstat = Path(os.environ["SystemRoot"]) / "System32" / "netstat.exe"
    connections = subprocess.run(
        [str(netstat), "-ano", "-p", "tcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=5,
    ).stdout
    listener = (
        rb"^[ \t]*TCP[ \t]+127\.0\.0\.1:(\d+)[ \t]+0\.0\.0\.0:0[ \t]+\S+[ \t]+"
        + str(pid).encode("ascii")
        + rb"[ \t\r]*$"
    )
    ports = re.findall(listener, connections, re.MULTILINE)
    if len(ports) == 1:
        return f"http://127.0.0.1:{int(ports[0])}/"
    return None


def yc_init(*, executable=None, profile=None, manual_browser=False):
    if manual_browser and os.name != "nt":
        raise YandexAIError("Ручное открытие браузера через этот скрипт доступно на Windows.")
    options = ("init", "--no-browser") if manual_browser else ("init",)
    command, env = yc_command(options, executable=executable, profile=profile)
    try:
        if not manual_browser:
            return subprocess.run(command, env=env).returncode
        with subprocess.Popen(command, env=env) as login:
            try:
                while login.poll() is None:
                    url = windows_login_url(login.pid)
                    if url:
                        print(f"\nОткрой {url} в браузере на этом ПК.", flush=True)
                        break
                    time.sleep(0.5)
                return login.wait()
            finally:
                if login.poll() is None:
                    login.terminate()
    except (OSError, subprocess.SubprocessError):
        raise YandexAIError("Не удалось запустить YC CLI или найти его порт входа.") from None


def get_iam_token(*, executable=None, profile=None):
    """Obtain a usable token from YC CLI without printing or writing it."""
    token = yc_read(("iam", "create-token"), executable=executable, profile=profile)
    if not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
        raise YandexAIError("YC CLI не вернул IAM-токен. Проверь вход через yc init.")
    return token


def ask_deepseek(prompt, *, folder_id=None, executable=None, profile=None):
    """Send a text prompt to DeepSeek using the subscription endpoint."""
    if not prompt.strip():
        raise YandexAIError("Передай текст запроса через --prompt или stdin.")
    if folder_id is None:
        folder_id = yc_read(("config", "get", "folder-id"), executable=executable, profile=profile)
    if not re.fullmatch(r"[a-zA-Z0-9-]+", folder_id):
        raise YandexAIError("Выбери каталог подписки в yc init или передай --folder-id.")

    body = json.dumps(
        {"model": f"gpt://{folder_id}/{MODEL}/latest", "input": prompt, "store": False}
    ).encode("utf-8")
    opener = build_opener(NoRedirect())
    for attempt in range(2):
        token = get_iam_token(executable=executable, profile=profile)
        request = Request(
            RESPONSES_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with opener.open(request, timeout=55) as response:
                result = json.load(response)
            break
        except HTTPError as error:
            status = error.code
            error.close()
            if status == 401 and attempt == 0:
                continue
            hint = {
                401: " Проверь вход под владельцем подписки.",
                403: " Проверь подписку, каталог и права пользователя.",
                429: " Проверь лимиты подписки и количество одновременных запросов.",
            }.get(status, "")
            raise YandexAIError(f"Yandex AI Studio вернул HTTP {status}.{hint}") from None
        except (URLError, OSError):
            raise YandexAIError("Не удалось получить ответ Yandex AI Studio по сети.") from None
        except (UnicodeError, ValueError):
            raise YandexAIError("Yandex AI Studio вернул некорректный JSON.") from None

    status = result.get("status") if isinstance(result, dict) else None
    if status != "completed":
        if status in ("failed", "incomplete", "cancelled", "queued", "in_progress"):
            raise YandexAIError(f"Yandex AI Studio завершил запрос со статусом {status}.")
        raise YandexAIError("В ответе Yandex AI Studio нет ожидаемого статуса.")
    for item in reversed(result.get("output", [])):
        if item.get("type") == "message":
            output = "\n".join(
                part["text"] for part in item.get("content", []) if part.get("type") == "output_text"
            )
            if output:
                return output
            break
    raise YandexAIError("В итоговом сообщении Yandex AI Studio нет текста.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yc", help="Path to the YC CLI executable")
    parser.add_argument("--profile", help="YC CLI profile name")
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init", help="Sign in to Yandex Cloud from your terminal")
    init.add_argument("--manual-browser", action="store_true", help="Print a local login URL on Windows")
    commands.add_parser("check", help="Check IAM token issuance without displaying the token")
    ask = commands.add_parser("ask", help="Ask DeepSeek via the subscription API")
    ask.add_argument("--folder-id", help="Subscription folder ID, defaults to the YC CLI profile")
    ask.add_argument("--prompt", help="Text prompt, defaults to stdin")
    run = commands.add_parser("run", help="Start a trusted program with YC_IAM_TOKEN")
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    yc = {"executable": args.yc, "profile": args.profile}
    try:
        if args.action == "init":
            return yc_init(manual_browser=args.manual_browser, **yc)
        elif args.action == "check":
            get_iam_token(**yc)
            print("IAM token OK")
        elif args.action == "ask":
            if args.prompt is None and sys.stdin.isatty():
                ask.error("supply --prompt or pipe the prompt through stdin")
            prompt = args.prompt if args.prompt is not None else sys.stdin.read()
            print(ask_deepseek(prompt, folder_id=args.folder_id, **yc))
        else:
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            if not command:
                run.error("supply a command after --")
            env = dict(os.environ, YC_IAM_TOKEN=get_iam_token(**yc))
            try:
                return subprocess.run(command, env=env).returncode
            except OSError:
                raise YandexAIError("Не удалось запустить клиент.") from None
    except YandexAIError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

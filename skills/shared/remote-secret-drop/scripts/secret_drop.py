#!/usr/bin/env python3
"""Launch, inspect, and stop a one-shot HTTPS secret-drop receiver on a remote server."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

KEY_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_VAL_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]+$")


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    validator: str = "nonempty"
    required: bool = True


def parse_field_spec(raw: str) -> FieldSpec:
    """Parse KEY[:Label[:validator[:optional]]] field specification."""
    parts = raw.split(":", 3)
    key = parts[0].strip()
    if not KEY_NAME_RE.match(key):
        raise ValueError(f"Invalid env key name: {key!r}")
    label = parts[1].strip() if len(parts) > 1 and parts[1].strip() else key
    validator = parts[2].strip() if len(parts) > 2 and parts[2].strip() else "nonempty"
    if validator not in ("nonempty", "telegram_bot", "tg_username") and not validator.startswith("regex:"):
        raise ValueError(f"Unsupported validator: {validator!r}")
    required = not (len(parts) > 3 and parts[3].strip().lower() == "optional")
    return FieldSpec(key=key, label=label, validator=validator, required=required)


def format_env_value(value: str) -> str:
    """Format a single-line .env value safely without shell/newline injection."""
    if "\n" in value or "\r" in value:
        raise ValueError("Secret values must be single-line")
    if value == "" or SAFE_VAL_RE.match(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_lines(existing_text: str, updates: dict[str, str]) -> str:
    """Update or append keys in .env content while preserving unrelated lines."""
    remaining = dict(updates)
    out_lines: list[str] = []
    for line in existing_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in remaining:
            out_lines.append(f"{k}={format_env_value(remaining.pop(k))}")
        else:
            out_lines.append(line)
    for k, v in remaining.items():
        out_lines.append(f"{k}={format_env_value(v)}")
    return "\n".join(out_lines) + ("\n" if out_lines else "")


def _to_git_bash_path(win_path: Path) -> str:
    s = str(win_path.resolve()).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        return f"/{s[0].lower()}{s[2:]}"
    return s


def _find_git_bash() -> str | None:
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _default_identity(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    cand = Path.home() / ".ssh" / "id_ed25519"
    return cand if cand.exists() else None


def run_ssh(
    *,
    host: str,
    ssh_port: int,
    user: str,
    identity: Path | None,
    remote_cmd: str,
    stdin_bytes: bytes | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[bytes]:
    """Run an SSH command reliably on macOS, Linux, and Cyrillic-profile Windows."""
    ssh_opts = [
        "-p", str(ssh_port),
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    target = f"{user}@{host}"

    if os.name == "nt":
        git_bash = _find_git_bash()
        if git_bash:
            parts = ["ssh"] + ssh_opts
            if identity:
                parts += ["-i", f'"{_to_git_bash_path(identity)}"']
            parts.append(target)
            # Pass remote command via base64 so quotes/UTF-8 never break
            b64_cmd = base64.b64encode(remote_cmd.encode("utf-8")).decode("ascii")
            parts.append(f'"echo {b64_cmd} | base64 -d | bash -s"')
            bash_line = " ".join(parts)
            return subprocess.run(
                [git_bash, "-c", bash_line],
                input=stdin_bytes,
                capture_output=True,
                timeout=timeout,
            )

    cmd = ["ssh"] + ssh_opts
    if identity:
        cmd += ["-i", str(identity)]
    cmd += [target, remote_cmd]
    return subprocess.run(cmd, input=stdin_bytes, capture_output=True, timeout=timeout)


REMOTE_TEMPLATE = r'''#!/usr/bin/env python3
import base64
import html
import json
import os
try:
    import pwd
except ImportError:
    pwd = None
import re
import secrets
import signal
import ssl
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CFG = json.loads(base64.b64decode("__CFG_B64__").decode("utf-8"))
SECRET = CFG["secret"]
PORT = int(CFG["drop_port"])
ENV_PATH = CFG["env_file"]
OWNER = CFG["owner"]
CERT = CFG["cert"]
KEY = CFG["key"]
TTL = int(CFG["ttl"])
OPEN_UFW = bool(CFG["open_ufw"])
SELF_SIGNED = bool(CFG["self_signed"])
EXTRA_PIN_KEY = CFG.get("extra_pin_key") or ""
FIELDS = CFG["fields"]
LOG_PATH = CFG["log_path"]
TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{25,}$")
TG_USER_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
SAFE_VAL_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]+$")


def log(msg: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def format_env_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Multiline value is not allowed")
    if value == "" or SAFE_VAL_RE.match(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env(env_path: str, owner: str, updates: dict) -> None:
    parent = os.path.dirname(env_path) or "."
    os.makedirs(parent, mode=0o750, exist_ok=True)
    if pwd is not None and hasattr(os, "chown"):
        pw = pwd.getpwnam(owner)
        os.chown(parent, pw.pw_uid, pw.pw_gid)
    else:
        pw = None
    existing = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8", errors="replace") as f:
            existing = f.read()
    remaining = dict(updates)
    out_lines = []
    for line in existing.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in remaining:
            out_lines.append(f"{k}={format_env_value(remaining.pop(k))}")
        else:
            out_lines.append(line)
    for k, v in remaining.items():
        out_lines.append(f"{k}={format_env_value(v)}")
    payload = ("\n".join(out_lines) + ("\n" if out_lines else "")).encode("utf-8")
    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    if pw is not None and hasattr(os, "chown"):
        os.chown(env_path, pw.pw_uid, pw.pw_gid)
    os.chmod(env_path, 0o600)


def verify_telegram_bot(token: str):
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe", method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
        if data.get("ok"):
            return data["result"].get("username", "unknown")
    return None


def validate_fields(form_data: dict):
    updates = {}
    notes = []
    for field in FIELDS:
        key = field["key"]
        label = field["label"]
        validator = field["validator"]
        required = field["required"]
        val = (form_data.get(key, [""])[0]).strip()
        if not val:
            if required:
                return None, None, f"Поле «{label}» обязательно."
            continue
        if "\n" in val or "\r" in val:
            return None, None, f"Поле «{label}» должно быть в одну строку."
        if validator == "telegram_bot":
            if not TOKEN_RE.match(val):
                return None, None, f"Поле «{label}» не похоже на токен Telegram-бота."
            try:
                bot_user = verify_telegram_bot(val)
            except Exception:
                return None, None, "Telegram API не подтвердил токен. Проверь, нет ли лишних символов."
            if not bot_user:
                return None, None, "Telegram API отклонил токен."
            notes.append(f"Бот @{bot_user} подтверждён.")
        elif validator == "tg_username":
            val = val.lstrip("@")
            if not TG_USER_RE.match(val):
                return None, None, f"Поле «{label}» — некорректный @username."
        elif validator.startswith("regex:"):
            pattern = validator[6:]
            if not re.match(pattern, val):
                return None, None, f"Поле «{label}» не соответствует формату."
        updates[key] = val
    return updates, notes, ""


def render_form(error: str = "") -> bytes:
    err_html = f'<div class="err">{html.escape(error)}</div>' if error else ""
    fields_html = []
    for f in FIELDS:
        key = html.escape(f["key"])
        label = html.escape(f["label"])
        req_attr = " required" if f["required"] else ""
        itype = "text" if f["validator"] == "tg_username" else "password"
        fields_html.append(
            f'<label for="{key}">{label}</label>'
            f'<input id="{key}" name="{key}" type="{itype}" autocomplete="off" autocapitalize="off" spellcheck="false"{req_attr}>'
        )
    doc = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Передача секрета</title><style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#f8fafc;margin:0;padding:24px 16px}'
        '.card{max-width:440px;margin:24px auto;background:#1e293b;border:1px solid #334155;border-radius:16px;padding:22px;box-shadow:0 12px 30px rgba(0,0,0,.35)}'
        'h1{font-size:20px;margin:0 0 10px}p{font-size:14px;color:#cbd5e1;line-height:1.45;margin:0 0 16px}'
        'label{display:block;font-size:13px;color:#94a3b8;margin:12px 0 6px}'
        'input{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid #475569;background:#0f172a;color:#f8fafc;font-size:15px}'
        'button{width:100%;margin-top:18px;padding:13px;border:0;border-radius:10px;background:#2563eb;color:#fff;font-size:16px;font-weight:600;cursor:pointer}'
        '.err{background:#7f1d1d;border:1px solid #ef4444;color:#fecaca;padding:10px 12px;border-radius:10px;font-size:14px;margin-bottom:12px}'
        '.note{font-size:12px;color:#94a3b8;margin-top:14px}'
        '</style></head><body><div class="card">'
        '<h1>Одноразовая передача данных</h1>'
        f'<p>Данные сохранятся напрямую на твой сервер в <code>{html.escape(ENV_PATH)}</code> (chmod 600). После отправки порт {PORT} закроется.</p>'
        f'{err_html}'
        f'<form method="post" action="/{SECRET}">'
        + "".join(fields_html)
        + '<button type="submit">Сохранить на сервер</button></form>'
        '<div class="note">Секреты не попадают в чат и логи агента.</div>'
        '</div></body></html>'
    )
    return doc.encode("utf-8")


def render_success(notes: list, extra_pin: str) -> bytes:
    notes_html = "".join(f"<p>{html.escape(n)}</p>" for n in notes)
    pin_html = (
        f'<p>Одноразовый код привязки:<br><code>/claim {html.escape(extra_pin)}</code></p>'
        if extra_pin
        else ""
    )
    doc = (
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Сохранено</title><style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#f8fafc;margin:0;padding:24px 16px}'
        '.card{max-width:440px;margin:24px auto;background:#1e293b;border:1px solid #22c55e;border-radius:16px;padding:22px}'
        'h1{font-size:20px;color:#4ade80;margin:0 0 12px}p{font-size:15px;line-height:1.5;color:#e2e8f0}'
        'code{background:#0f172a;padding:4px 8px;border-radius:6px;font-size:15px;color:#fde047}'
        '</style></head><body><div class="card">'
        '<h1>Сохранено</h1>'
        f'{notes_html}'
        f'<p>Файл <code>{html.escape(ENV_PATH)}</code> обновлён, временный порт {PORT} закрывается.</p>'
        f'{pin_html}'
        '<p>Теперь вернись в чат и напиши агенту: <b>готово</b>.</p>'
        '</div></body></html>'
    )
    return doc.encode("utf-8")


class DropHandler(BaseHTTPRequestHandler):
    server_version = "SecretDrop/1.0"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != f"/{SECRET}":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        self._send(200, render_form())

    def do_POST(self):
        if self.path != f"/{SECRET}":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 8192:
            self._send(400, render_form("Некорректный размер запроса."))
            return
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = urllib.parse.parse_qs(raw, keep_blank_values=True)
        updates, notes, err = validate_fields(form)
        if err:
            self._send(400, render_form(err))
            return
        extra_pin = ""
        if EXTRA_PIN_KEY:
            extra_pin = f"{secrets.randbelow(900000) + 100000}"
            updates[EXTRA_PIN_KEY] = extra_pin
        upsert_env(ENV_PATH, OWNER, updates)
        log(f"SECRET_SAVED keys={','.join(sorted(updates.keys()))}")
        self._send(200, render_success(notes, extra_pin))
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def main():
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), DropHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    def stop_timeout():
        log("DROP_TIMEOUT")
        httpd.shutdown()

    timer = threading.Timer(TTL, stop_timeout)
    timer.daemon = True
    timer.start()

    def handle_sig(signum, frame):
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_sig)
    log("DROP_READY")
    try:
        httpd.serve_forever()
    finally:
        timer.cancel()
        httpd.server_close()
        if OPEN_UFW:
            subprocess.run(["ufw", "delete", "allow", f"{PORT}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if SELF_SIGNED:
            for p in (CERT, KEY):
                try:
                    os.remove(p)
                except OSError:
                    pass
        try:
            os.remove(__file__)
        except OSError:
            pass
        log("DROP_CLOSED")


if __name__ == "__main__":
    main()
'''


def build_remote_script(cfg: dict) -> str:
    b64 = base64.b64encode(json.dumps(cfg, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return REMOTE_TEMPLATE.replace("__CFG_B64__", b64)


def cmd_start(args: argparse.Namespace) -> int:
    fields = [parse_field_spec(f) for f in args.field]
    identity = _default_identity(args.identity)
    domain = args.domain or args.host
    owner = args.owner or args.user
    secret = secrets.token_urlsafe(24)
    tag = secrets.token_hex(4)
    remote_py = f"/tmp/secret_drop_{args.drop_port}.py"
    log_path = f"/tmp/secret_drop_{args.drop_port}.log"

    if not args.self_signed and (not args.cert or not args.key):
        print("ERROR: pass both --cert and --key, or use --self-signed", file=sys.stderr)
        return 2

    cert_path = args.cert or f"/tmp/secret_drop_{args.drop_port}_{tag}.crt"
    key_path = args.key or f"/tmp/secret_drop_{args.drop_port}_{tag}.key"

    # 1. Stop any prior drop listener on same port & verify port is genuinely free
    pre_cmd = f"""
set -euo pipefail
sudo -n pkill -f '/tmp/secret_drop_{args.drop_port}\\.py' 2>/dev/null || true
sleep 1
if ss -lnt | awk '{{print $4}}' | grep -qE '[:.]{args.drop_port}$'; then
  echo "PORT_BUSY"
  exit 10
fi
"""
    if args.self_signed:
        pre_cmd += f"""
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout "{key_path}" -out "{cert_path}" -days 1 -subj "/CN={domain}" >/dev/null 2>&1
sudo -n chown root:root "{key_path}" "{cert_path}"
sudo -n chmod 600 "{key_path}"
"""
    else:
        pre_cmd += f'sudo -n test -r "{cert_path}" && sudo -n test -r "{key_path}"\n'

    pre_res = run_ssh(
        host=args.host, ssh_port=args.ssh_port, user=args.user, identity=identity, remote_cmd=pre_cmd
    )
    if pre_res.returncode != 0:
        sys.stdout.buffer.write(pre_res.stdout)
        sys.stderr.buffer.write(pre_res.stderr)
        return pre_res.returncode

    cfg = {
        "secret": secret,
        "drop_port": args.drop_port,
        "env_file": args.env_file,
        "owner": owner,
        "cert": cert_path,
        "key": key_path,
        "ttl": args.ttl,
        "open_ufw": not args.no_ufw,
        "self_signed": args.self_signed,
        "extra_pin_key": args.extra_pin_key or "",
        "log_path": log_path,
        "fields": [
            {"key": f.key, "label": f.label, "validator": f.validator, "required": f.required}
            for f in fields
        ],
    }
    remote_script = build_remote_script(cfg).encode("utf-8")

    # 2. Upload script
    up_res = run_ssh(
        host=args.host,
        ssh_port=args.ssh_port,
        user=args.user,
        identity=identity,
        remote_cmd=f'sudo -n tee "{remote_py}" >/dev/null && sudo -n chmod 700 "{remote_py}"',
        stdin_bytes=remote_script,
    )
    if up_res.returncode != 0:
        sys.stderr.buffer.write(up_res.stderr)
        return up_res.returncode

    # 3. Open ufw if requested and start detached server
    ufw_open_cmd = (
        f"sudo -n ufw allow {args.drop_port}/tcp comment 'remote-secret-drop' >/dev/null"
        if not args.no_ufw
        else "true"
    )
    start_cmd = f"""
set -euo pipefail
sudo -n rm -f "{log_path}" /tmp/secret_drop_{args.drop_port}_nohup.log
{ufw_open_cmd}
sudo -n setsid python3 "{remote_py}" >/tmp/secret_drop_{args.drop_port}_nohup.log 2>&1 </dev/null &
sleep 1
ss -lntup | grep ':{args.drop_port}' || true
sudo -n cat "{log_path}" 2>/dev/null || true
"""
    st_res = run_ssh(
        host=args.host, ssh_port=args.ssh_port, user=args.user, identity=identity, remote_cmd=start_cmd
    )
    print(st_res.stdout.decode("utf-8", errors="replace").strip())
    if st_res.returncode != 0:
        print(st_res.stderr.decode("utf-8", errors="replace").strip(), file=sys.stderr)
        return st_res.returncode

    # 4. External HTTPS verification
    url = f"https://{domain}:{args.drop_port}/{secret}"
    wrong_url = f"https://{domain}:{args.drop_port}/wrong"
    ssl_ctx = None
    if args.self_signed:
        import ssl as _ssl
        ssl_ctx = _ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(url, timeout=10, context=ssl_ctx) as r:
            body = r.read().decode("utf-8", errors="replace")
            print(f"EXT_GET_STATUS: {r.status} FORM_OK: {secret in body}")
    except Exception as exc:
        print(f"EXT_GET_ERR: {exc}", file=sys.stderr)
        return 1

    try:
        urllib.request.urlopen(wrong_url, timeout=10, context=ssl_ctx)
        print("WRONG_PATH_STATUS: 200 (unexpected)", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as e:
        print(f"WRONG_PATH_STATUS: {e.code}")

    print(f"DROP_URL: {url}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    identity = _default_identity(args.identity)
    log_path = f"/tmp/secret_drop_{args.drop_port}.log"
    remote_cmd = f"""
sudo -n cat "{log_path}" 2>/dev/null || echo "NO_LOG"
echo "---UFW---"
sudo -n ufw status | grep '{args.drop_port}/tcp' || echo "UFW_CLOSED"
echo "---SS---"
ss -lntup | grep ':{args.drop_port}' || echo "PORT_CLOSED"
"""
    if args.env_file:
        remote_cmd += f"""
echo "---ENV_KEYS---"
if [ -f "{args.env_file}" ]; then
  ls -la "{args.env_file}"
  cut -d= -f1 "{args.env_file}"
else
  echo "ENV_MISSING"
fi
"""
    res = run_ssh(
        host=args.host, ssh_port=args.ssh_port, user=args.user, identity=identity, remote_cmd=remote_cmd
    )
    print(res.stdout.decode("utf-8", errors="replace").strip())
    if res.returncode != 0:
        print(res.stderr.decode("utf-8", errors="replace").strip(), file=sys.stderr)
    return res.returncode


def cmd_stop(args: argparse.Namespace) -> int:
    identity = _default_identity(args.identity)
    remote_cmd = f"""
sudo -n pkill -f '/tmp/secret_drop_{args.drop_port}\\.py' 2>/dev/null || true
sleep 1
sudo -n ufw delete allow {args.drop_port}/tcp >/dev/null 2>&1 || true
sudo -n rm -f /tmp/secret_drop_{args.drop_port}.py /tmp/secret_drop_{args.drop_port}_*.crt /tmp/secret_drop_{args.drop_port}_*.key
echo "STOPPED"
"""
    res = run_ssh(
        host=args.host, ssh_port=args.ssh_port, user=args.user, identity=identity, remote_cmd=remote_cmd
    )
    print(res.stdout.decode("utf-8", errors="replace").strip())
    if res.returncode != 0:
        print(res.stderr.decode("utf-8", errors="replace").strip(), file=sys.stderr)
    return res.returncode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="One-shot HTTPS secret drop on a remote server.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_ssh_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--host", required=True)
        sp.add_argument("--ssh-port", type=int, default=22)
        sp.add_argument("--user", default="root")
        sp.add_argument("--identity")
        sp.add_argument("--drop-port", type=int, default=8450)

    s = sub.add_parser("start", help="Launch temporary HTTPS secret drop")
    add_ssh_args(s)
    s.add_argument("--domain", help="Domain matching TLS certificate")
    s.add_argument("--cert", help="Path to fullchain.pem on remote server")
    s.add_argument("--key", help="Path to privkey/key.pem on remote server")
    s.add_argument("--self-signed", action="store_true", help="Generate temporary self-signed cert")
    s.add_argument("--env-file", required=True, help="Target .env path on remote server")
    s.add_argument("--owner", help="File owner on remote server (defaults to --user)")
    s.add_argument("--field", action="append", required=True, help="KEY[:Label[:validator[:optional]]]")
    s.add_argument("--extra-pin-key", help="Generate 6-digit PIN and store under this env key")
    s.add_argument("--ttl", type=int, default=600, help="Auto-expire timeout in seconds")
    s.add_argument("--no-ufw", action="store_true", help="Do not modify ufw rules")

    st = sub.add_parser("status", help="Inspect drop state and .env key names (never values)")
    add_ssh_args(st)
    st.add_argument("--env-file", help="Optional .env path to list key names only")

    sp = sub.add_parser("stop", help="Force-stop drop server and close ufw rule")
    add_ssh_args(sp)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "start":
        return cmd_start(args)
    if args.cmd == "status":
        return cmd_status(args)
    if args.cmd == "stop":
        return cmd_stop(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

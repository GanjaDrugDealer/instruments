"""List DeepSeek models or send one chat request."""

import argparse
import base64
import binascii
import ctypes
import ctypes.wintypes
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_unprotect(blob):
    """Decrypt a DPAPI blob for the current Windows user, without spawning processes."""
    buffer = ctypes.create_string_buffer(bytes(blob), len(blob))
    source = DataBlob(len(blob), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def read_saved_key(path):
    """Read a key saved by save-key.ps1 (Export-Clixml of a SecureString)."""
    raw = path.read_bytes()
    text = ""
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            candidate = raw.decode(encoding)
        except UnicodeError:
            continue
        if "<SS>" in candidate:
            text = candidate
            break
    if not text:
        return ""
    start = text.find("<SS>") + len("<SS>")
    blob_text = text[start : text.find("</SS>", start)].strip()
    if not blob_text:
        return ""
    try:
        blob = bytes.fromhex(blob_text)
    except ValueError:
        try:
            blob = base64.b64decode(blob_text, validate=True)
        except (binascii.Error, ValueError):
            return ""
    return dpapi_unprotect(blob).decode("utf-16-le", "replace")


def key_file_candidates():
    """Plaintext key files that survive any session, shell or launcher."""
    explicit = os.environ.get("DEEPSEEK_API_KEY_FILE", "").strip()
    if explicit:
        yield Path(explicit)
    yield Path.home() / ".config" / "deepseek" / "api-key.txt"


def read_windows_key():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        saved = Path(local_app_data) / "DeepSeek" / "api-key.xml"
        if saved.is_file():
            try:
                key = read_saved_key(saved)
            except (OSError, UnicodeError, ValueError):
                key = ""
            if key:
                return key
    for candidate in key_file_candidates():
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8-sig").strip()
            except OSError:
                continue
    return ""


def read_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key and os.name == "nt":
        key = read_windows_key()
    if not key:
        raise RuntimeError(
            "Set DEEPSEEK_API_KEY, save the key with scripts/save-key.ps1, "
            "or put it in ~/.config/deepseek/api-key.txt."
        )
    if not key.isascii() or not key.isprintable() or any(char.isspace() for char in key):
        raise RuntimeError("DeepSeek API key has invalid characters.")
    return key


def call_api(route, key, body=None):
    headers = {"Authorization": f"Bearer {key}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    request = Request(f"{BASE_URL}/{route}", data=data, headers=headers)
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        result = json.load(response)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("models", help="list model IDs")
    chat = commands.add_parser("chat", help="send a request read from stdin")
    chat.add_argument("--model", default=DEFAULT_MODEL)
    chat.add_argument("--max-tokens", type=int, default=512)
    chat.add_argument("--json", action="store_true", help="return a validated JSON object")
    args = parser.parse_args()

    if args.command == "chat":
        if args.max_tokens < 1:
            chat.error("--max-tokens must be positive")
        prompt = sys.stdin.read().strip()
        if not prompt:
            chat.error("provide a prompt on stdin")

    try:
        key = read_api_key()
        if args.command == "models":
            result = call_api("models", key)
            print("\n".join(sorted({model["id"] for model in result["data"]})))
        else:
            messages = [{"role": "user", "content": prompt}]
            body = {
                "model": args.model,
                "max_tokens": args.max_tokens,
                "messages": messages,
                "thinking": {"type": "disabled"},
            }
            if args.json:
                messages.insert(0, {"role": "system", "content": "Return a JSON object."})
                body["response_format"] = {"type": "json_object"}
            result = call_api("chat/completions", key, body)
            choice = result["choices"][0]
            if choice["finish_reason"] != "stop":
                raise RuntimeError("DeepSeek did not finish the response. Check the output limit.")
            text = choice["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("DeepSeek returned no text. Check the model and output limit.")
            if args.json:
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise RuntimeError("DeepSeek response is not a JSON object.")
            print(text)
    except HTTPError as exc:
        parser.exit(1, f"DeepSeek HTTP {exc.code}\n")
    except (URLError, TimeoutError):
        parser.exit(1, "Could not reach DeepSeek or the request timed out.\n")
    except (ValueError, KeyError, IndexError, TypeError):
        parser.exit(1, "DeepSeek response could not be read.\n")
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

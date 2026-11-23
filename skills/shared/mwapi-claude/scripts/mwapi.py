"""Discover MWAPI models or send one text chat request."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://api.mwapi.dev/v1"
DEFAULT_MODEL = "claude-haiku-5-5"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_windows_key():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data or not (Path(local_app_data) / "MWAPI" / "api-key.xml").is_file():
        return ""

    command = (
        "$ErrorActionPreference = 'Stop'\n"
        "$path = Join-Path $env:LOCALAPPDATA 'MWAPI\\api-key.xml'\n"
        "$secret = Import-Clixml -LiteralPath $path\n"
        "if ($secret -isnot [securestring]) { exit 1 }\n"
        "[Console]::Write([System.Net.NetworkCredential]::new('', $secret).Password)\n"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise RuntimeError("Cannot open the saved MWAPI key under this Windows user.") from None
    return result.stdout.strip()


def read_api_key():
    key = os.environ.get("MWAPI_API_KEY", "").strip()
    if not key and os.name == "nt":
        key = read_windows_key()
    if not key:
        raise RuntimeError("Set MWAPI_API_KEY or use a saved Windows key.")
    if not key.isascii() or not key.isprintable() or any(char.isspace() for char in key):
        raise RuntimeError("MWAPI API key has invalid characters.")
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
            result = call_api("chat/completions", key, {
                "model": args.model,
                "max_tokens": args.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            })
            text = result["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("MWAPI returned no text. Check the model and output limit.")
            print(text)
    except HTTPError as exc:
        parser.exit(1, f"MWAPI HTTP {exc.code}\n")
    except (URLError, TimeoutError):
        parser.exit(1, "Could not reach MWAPI or the request timed out.\n")
    except (ValueError, KeyError, IndexError, TypeError):
        parser.exit(1, "MWAPI response could not be read.\n")
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()

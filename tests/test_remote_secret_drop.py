"""Tests for remote-secret-drop skill script and embedded receiver."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "shared" / "remote-secret-drop" / "scripts" / "secret_drop.py"

sys.path.insert(0, str(SCRIPT.parent))
import secret_drop  # noqa: E402


class SecretDropUnitTest(unittest.TestCase):
    def test_parse_field_spec_and_upsert_env(self) -> None:
        f = secret_drop.parse_field_spec("BOT_TOKEN:Токен:telegram_bot")
        self.assertEqual(f.key, "BOT_TOKEN")
        self.assertEqual(f.label, "Токен")
        self.assertEqual(f.validator, "telegram_bot")
        self.assertTrue(f.required)

        f_opt = secret_drop.parse_field_spec("ADMIN_USERNAME:Ник:tg_username:optional")
        self.assertFalse(f_opt.required)

        existing = "# comment\nWB_PROXY_URL=http://user:pass@127.0.0.1:8448\nBOT_TOKEN=old\n"
        updated = secret_drop.upsert_env_lines(
            existing, {"BOT_TOKEN": "123:abc_XYZ", "CLAIM_PIN": "654321"}
        )
        self.assertIn("# comment", updated)
        self.assertIn("WB_PROXY_URL=http://user:pass@127.0.0.1:8448", updated)
        self.assertIn("BOT_TOKEN=123:abc_XYZ", updated)
        self.assertIn("CLAIM_PIN=654321", updated)
        self.assertNotIn("BOT_TOKEN=old", updated)

        with self.assertRaises(ValueError):
            secret_drop.upsert_env_lines("", {"BAD": "line1\nEVIL=1"})

    def test_remote_script_compiles_and_renders(self) -> None:
        cfg = {
            "secret": secrets.token_urlsafe(12),
            "drop_port": 18450,
            "env_file": "/tmp/fake.env",
            "owner": "root",
            "cert": "/tmp/cert.pem",
            "key": "/tmp/key.pem",
            "ttl": 60,
            "open_ufw": False,
            "self_signed": False,
            "extra_pin_key": "CLAIM_PIN",
            "log_path": "/tmp/fake.log",
            "fields": [
                {"key": "API_KEY", "label": "API Key", "validator": "nonempty", "required": True}
            ],
        }
        code = secret_drop.build_remote_script(cfg)
        compile(code, "remote_drop_test.py", "exec")
        self.assertIn("DropHandler", code)

    def test_live_https_drop_flow(self) -> None:
        openssl = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        if not Path(openssl).exists():
            self.skipTest("openssl not available")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cert = tmp / "cert.pem"
            key = tmp / "key.pem"
            env_file = tmp / "app.env"
            env_file.write_text("KEEP_ME=yes\nAPI_KEY=old\n", encoding="utf-8")
            subprocess.run(
                [
                    openssl, "req", "-x509", "-newkey", "ec",
                    "-pkeyopt", "ec_paramgen_curve:prime256v1",
                    "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-subj", "/CN=127.0.0.1",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            secret = secrets.token_urlsafe(16)
            cfg = {
                "secret": secret,
                "drop_port": 0,
                "env_file": str(env_file),
                "owner": "ignored",
                "cert": str(cert),
                "key": str(key),
                "ttl": 30,
                "open_ufw": False,
                "self_signed": False,
                "extra_pin_key": "CLAIM_PIN",
                "log_path": str(tmp / "drop.log"),
                "fields": [
                    {"key": "API_KEY", "label": "API Key", "validator": "nonempty", "required": True}
                ],
            }
            ns: dict = {}
            code = secret_drop.build_remote_script(cfg)
            exec(compile(code, "remote_drop_live.py", "exec"), ns)
            if ns.get("pwd") is not None:
                ns["pwd"].getpwnam = lambda _name: type("P", (), {"pw_uid": 0, "pw_gid": 0})()
            ns["os"].chown = lambda *_a, **_kw: None

            import ssl
            import threading
            from http.server import ThreadingHTTPServer

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), ns["DropHandler"])
            port = httpd.server_address[1]
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(cert), str(key))
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                client_ctx = ssl._create_unverified_context()
                with self.assertRaises(urllib.error.HTTPError) as cm404:
                    urllib.request.urlopen(f"https://127.0.0.1:{port}/wrong", context=client_ctx, timeout=5)
                self.assertEqual(cm404.exception.code, 404)

                with urllib.request.urlopen(f"https://127.0.0.1:{port}/{secret}", context=client_ctx, timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    self.assertIn(secret, r.read().decode("utf-8"))

                bad_data = urllib.parse.urlencode({"API_KEY": "   "}).encode("utf-8")
                with self.assertRaises(urllib.error.HTTPError) as cm400:
                    urllib.request.urlopen(
                        f"https://127.0.0.1:{port}/{secret}", data=bad_data, context=client_ctx, timeout=5
                    )
                self.assertEqual(cm400.exception.code, 400)

                good_data = urllib.parse.urlencode({"API_KEY": "super_secret_42"}).encode("utf-8")
                with urllib.request.urlopen(
                    f"https://127.0.0.1:{port}/{secret}", data=good_data, context=client_ctx, timeout=5
                ) as r:
                    self.assertEqual(r.status, 200)
                    body = r.read().decode("utf-8")
                    self.assertIn("/claim ", body)

                t.join(timeout=5)
                self.assertFalse(t.is_alive())
                saved = env_file.read_text(encoding="utf-8")
                self.assertIn("KEEP_ME=yes", saved)
                self.assertIn("API_KEY=super_secret_42", saved)
                self.assertIn("CLAIM_PIN=", saved)
            finally:
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()

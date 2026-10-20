"""Check startup using only source and public env templates, without services."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.core.environment import resolve_env_file


BACKEND = Path(__file__).resolve().parents[2]


class LocalStartupTest(unittest.TestCase):
    def test_env_selection_and_missing_explicit_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / ".env.example").touch()
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(resolve_env_file(base), base / ".env.example")
                (base / ".env").touch()
                self.assertEqual(resolve_env_file(base), base / ".env")
            with patch.dict(os.environ, {"CTG_ENV_FILE": ".env.example"}, clear=True):
                self.assertEqual(resolve_env_file(base), base / ".env.example")
            with patch.dict(os.environ, {"CTG_ENV_FILE": "missing.env"}, clear=True):
                with self.assertRaises(FileNotFoundError):
                    resolve_env_file(base)

    def test_clean_checkout_starts_with_public_templates_without_network(self):
        script = """
import sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
with patch('socket.socket.connect', side_effect=AssertionError('Unexpected network call')):
    import run_server
    with patch('uvicorn.run') as serve:
        run_server.main()
        assert serve.call_args.kwargs['port'] == 18080
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get('/openapi.json')
        assert response.status_code == 200
        assert '/documents/acl/sync' in response.json()['paths']
"""
        for selected in (None, ".env.example", ".env.dummy"):
            with self.subTest(env=selected), tempfile.TemporaryDirectory() as directory:
                base = Path(directory) / "backend"
                base.mkdir()
                shutil.copytree(BACKEND / "app", base / "app", ignore=shutil.ignore_patterns("__pycache__"))
                for name in ("run_server.py", ".env.example", ".env.dummy"):
                    shutil.copy2(BACKEND / name, base / name)
                # An explicit template must win even if a broken private .env exists.
                if selected:
                    (base / ".env").write_text("DATABASE_URL=invalid\n", encoding="utf-8")
                env = os.environ.copy()
                for line in (base / ".env.example").read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.startswith("#"):
                        env.pop(line.split("=", 1)[0], None)
                env.pop("CTG_ENV_FILE", None)
                if selected:
                    env["CTG_ENV_FILE"] = selected
                completed = subprocess.run(
                    [sys.executable, "-c", script, str(base)], cwd=directory,
                    env=env, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

"""Resolve the same env file for direct ASGI startup and run_server.py."""
import os
import sys
from pathlib import Path


def get_backend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_env_file(base_dir: Path | None = None) -> Path:
    base_dir = base_dir or get_backend_dir()
    selected = os.getenv("CTG_ENV_FILE")
    if selected:
        path = Path(selected)
        path = path if path.is_absolute() else base_dir / path
        if not path.is_file():
            raise FileNotFoundError(f"CTG_ENV_FILE does not exist: {path}")
        return path
    for name in (".env", ".env.example", ".env.dummy"):
        path = base_dir / name
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"No environment file found in {base_dir}. Provide .env or .env.example."
    )

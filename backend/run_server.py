
import os
import sys
import multiprocessing
from pathlib import Path

from dotenv import load_dotenv


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def main():
    # Use the same selection as app.core.settings, including local templates.
    base_dir = get_base_dir()
    from app.core.environment import resolve_env_file

    env_file = resolve_env_file(base_dir)

    load_dotenv(
        dotenv_path=env_file,
        override=False,
    )

    # Import after loading environment variables
    import uvicorn
    from app.main import app

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "18080"))

    print("=" * 50)
    print("CTG AI Backend")
    print(f"Environment: {env_file}")
    print(f"Local URL: http://{host}:{port}")
    print("=" * 50)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        workers=1,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

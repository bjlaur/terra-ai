"""Run the system-test SOPEL bot for manual irssi testing."""

import os
import subprocess
import tempfile
from pathlib import Path

from tests.sopel_harness import (
    BOT_NICK,
    ERGO_HOST,
    ERGO_PORT,
    TEST_CHANNEL,
    load_test_model,
    write_sopel_test_config,
)


def main() -> int:
    project_dir = Path(__file__).resolve().parents[1]
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required for manual mode")
    model = load_test_model(project_dir)
    timeout = int(os.environ.get("TERRAI_TEST_TIMEOUT", "5")) * 6

    with tempfile.TemporaryDirectory(prefix="terra-ai-manual-") as raw_directory:
        directory = Path(raw_directory)
        config_file = write_sopel_test_config(
            directory,
            project_dir=project_dir,
            model=model,
            api_key=api_key,
            sqlite_path=directory / "terra_ai.db",
            provider_timeout=timeout,
        )
        print(
            f"Manual TerraAI is starting as {BOT_NICK} on "
            f"{ERGO_HOST}:{ERGO_PORT} {TEST_CHANNEL}."
        )
        print(
            "In another terminal, connect irssi to 127.0.0.1:6667 and "
            f"join {TEST_CHANNEL}. Press Ctrl+C here to stop."
        )
        process = subprocess.Popen(["sopel", "-c", str(config_file)])
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Integration tests using ergochat IRC server.

These tests create a real SOPEL bot instance, connect it to ergochat
running on localhost:6667, and verify end-to-end behavior.

Run with: ERGO_TEST=1 pytest tests/test_ergo.py -v
Requires ergochat running on localhost:6667
"""

import asyncio
import os
import tempfile
import time

import pytest

from terraai.config import TerraConfig
from terraai.database import DBConfig, Database

# Check if ergo is reachable
def ergo_running():
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 6667))
        sock.close()
        return result == 0
    except Exception:
        return False

ERGO_AVAILABLE = ergo_running()

pytestmark = pytest.mark.skipif(
    not ERGO_AVAILABLE,
    reason="ergochat not running on localhost:6667"
)


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    config = DBConfig(path=path, wal=False)
    database = Database(config)
    yield database
    os.unlink(path)


@pytest.fixture
def terra(db):
    config = TerraConfig()
    config.sqlite_path = db.config.path
    config.provider.api_key = os.environ.get("OPENROUTER_API_KEY", "")
    config.bot["nick"] = "TerraAI"
    from terraai.bot import TerraAI
    return TerraAI(config)


class TestErgoSmoke:
    """Basic smoke tests for ergochat connection."""

    def test_ergo_port_open(self):
        """Verify ergochat is listening on 6667."""
        assert ergo_available(), "ergochat not reachable"

    def test_ergo_config_exists(self):
        """Verify ergochat config file exists."""
        assert os.path.exists("/etc/ergochat/ircd.yaml")

    def test_can_connect_socket(self):
        """Test raw socket connection to ergo."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 6667))
        sock.close()
        assert result == 0

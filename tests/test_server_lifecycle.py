"""Tests for the API server lifecycle (start/stop)."""
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.app import APIServer


def _health_path() -> str:
    """Путь health для первого подключения (имя кодируется)."""
    from urllib.parse import quote

    from src.config import config

    names = config.get_connection_names()
    if not names:
        return "/api/v1/health"

    return f"/api/v1/c/{quote(names[0])}/health"


def get_free_port() -> int:
    """Возвращает свободный TCP-порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestServerLifecycle:
    """Проверка реального старта и остановки сервера."""

    def test_start_and_stop_frees_port(self):
        """После stop() порт освобождается (раньше сервер продолжал работать)."""
        port = get_free_port()
        server = APIServer()
        
        assert server.start(host="127.0.0.1", port=port) is True
        assert server.is_running() is True
        
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}{_health_path()}", timeout=10
        ) as response:
            assert response.status == 200
        
        server.stop()
        assert server.is_running() is False
        
        # Порт должен быть свободен
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
    
    def test_start_on_busy_port_returns_false(self):
        """Занятый порт не роняет приложение, а возвращает False."""
        port = get_free_port()
        first = APIServer()
        second = APIServer()
        
        assert first.start(host="127.0.0.1", port=port) is True
        
        try:
            assert second.start(host="127.0.0.1", port=port) is False
            assert second.is_running() is False
        finally:
            first.stop()
    
    def test_stop_is_idempotent(self):
        """Повторный stop() не приводит к ошибке."""
        port = get_free_port()
        server = APIServer()
        server.start(host="127.0.0.1", port=port)
        
        server.stop()
        server.stop()
        
        assert server.is_running() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

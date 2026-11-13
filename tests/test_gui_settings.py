"""Тесты настроек GUI: размер окна и перезапуск API при сохранении."""
import socket
import sys
import urllib.request
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def free_port() -> int:
    """Возвращает свободный TCP-порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _health_path() -> str:
    """Путь health для первого подключения (имя кодируется)."""
    from urllib.parse import quote

    from src.config import config

    names = config.get_connection_names()
    if not names:
        return "/api/v1/health"

    return f"/api/v1/c/{quote(names[0])}/health"


@pytest.fixture
def app(isolated_config):
    """Создаёт окно приложения или пропускает тест без графики."""
    from src.gui.main_window import MainWindow

    try:
        window = MainWindow(api_server=None)
    except Exception as e:
        pytest.skip(f"Не удалось создать окно Tk: {e}")

    yield window

    try:
        window.destroy()
    except Exception:
        pass


class TestWindowSize:
    """Размер окна: по умолчанию, изменение и запоминание."""

    def test_window_is_resizable(self, app):
        """Окно можно растягивать."""
        assert app.resizable() == (True, True)

    def test_window_size_saved_to_config(self, app):
        """Новый размер окна сохраняется в конфиг."""
        from src.config import config

        app.geometry("800x640")
        app.update()
        app._window_size = (800, 640)
        app._save_window_size()

        assert config.gui.get("width") == 800
        assert config.gui.get("height") == 640


class TestRestartApiOnSave:
    """Изменение настроек перезапускает API."""

    def test_save_settings_restarts_api(self, app):
        """После «Сохранить настройки» сервер перезапущен и отвечает."""
        from src.app import APIServer
        from src.config import config

        port = free_port()
        server = APIServer(gui_reference=app)

        assert server.start(host="127.0.0.1", port=port) is True
        app.api_server = server

        app.entry_api_host.delete(0, "end")
        app.entry_api_host.insert(0, "127.0.0.1")
        app.entry_api_port.delete(0, "end")
        app.entry_api_port.insert(0, str(port))

        try:
            app._save_settings()

            assert server.is_running() is True
            assert config.api.get("port") == port

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{_health_path()}", timeout=10
            ) as response:
                assert response.status == 200
        finally:
            server.stop()

    def test_restart_without_running_server_is_noop(self, app):
        """Если сервер не запущен, перезапуск ничего не делает."""
        app.api_server = None

        assert app._restart_api() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

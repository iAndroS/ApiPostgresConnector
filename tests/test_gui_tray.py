"""Тесты трея: время последней активности обновляется по запросам к API."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


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


class TestTrayActivity:
    """Последняя активность в трее."""

    def test_activity_updates_last_activity_time(self, app):
        """Запрос к API обновляет время последней активности."""
        import src.api.routes as routes_module
        from src.gui import main_window as mw

        mw._last_activity_time = None
        routes_module._gui_reference = app

        try:
            routes_module._notify_activity()
        finally:
            routes_module._gui_reference = None

        assert mw._last_activity_time is not None

    def test_tooltip_contains_activity(self, app):
        """Подсказка трея содержит время последней активности."""
        from src.gui import main_window as mw

        mw._last_activity_time = None
        text = app._tray_tooltip_text()

        assert "Последняя активность" in text
        assert "нет запросов" in text

    def test_tooltip_shows_connections_count(self, app):
        """В подсказке трея видно количество подключений."""
        from src.config import config

        text = app._tray_tooltip_text()

        assert f"Подключений: {len(config.connections)}" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

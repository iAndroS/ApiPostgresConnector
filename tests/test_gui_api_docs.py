"""Тесты вкладки «Документация API»: карточки, кнопки и переключатель подключений."""
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


class TestApiDocs:
    """Проверка карточек документации."""

    def test_endpoints_are_rendered(self, app):
        """Карточки всех эндпоинтов созданы."""
        assert len(app.docs_cards) == 9

    def test_every_endpoint_has_copy_buttons(self, app):
        """У каждого эндпоинта есть кнопки «Ссылка» и «cURL»."""
        for card in app.docs_cards:
            assert card["link_button"].cget("text") == "📋 Ссылка"
            assert card["curl_button"].cget("text") == "cURL"

    def test_browser_button_only_for_public_endpoints(self, app):
        """Кнопка «Открыть в браузере» — только у эндпоинтов без авторизации."""
        with_browser = [c for c in app.docs_cards if c["browser_button"] is not None]
        
        assert len(with_browser) == 2
        assert all(not c["requires_auth"] for c in with_browser)

    def test_links_contain_base_url(self, app):
        """В карточках есть ссылка с базовым URL."""
        for card in app.docs_cards:
            assert card["url"].startswith("http://")
            assert "/api/v1" in card["url"]

    def test_curl_command_contains_key(self, app):
        """curl-команда защищённых эндпоинтов содержит заголовок с ключом."""
        from src.config import config

        connection = config.get_connection(config.default_connection) or {}
        key = (connection.get("api_keys") or [""])[0]
        
        for card in app.docs_cards:
            if card["requires_auth"]:
                assert "X-API-Key" in card["curl"]
                if key:
                    assert key in card["curl"]
            else:
                assert "X-API-Key" not in card["curl"]


class TestConnectionSwitcher:
    """Проверка переключателя подключений в документации."""

    def test_switcher_lists_connections(self, app):
        """Переключатель содержит все подключения."""
        values = app.docs_connection_menu.cget("values")
        
        assert values == app._docs_connection_values()
        assert len(values) >= 1

    def test_switching_changes_links(self, app):
        """При смене подключения ссылки меняются."""
        from src.config import config

        name = "ТестовоеПодключение"
        created = False
        
        if config.get_connection(name) is None:
            config.add_connection(name, database={"host": "other-host"}, api_keys=["other-key"])
            created = True
        
        app._refresh_api_docs()
        
        try:
            before = [card["url"] for card in app.docs_cards]
            
            app.docs_connection_var.set(name)
            app._on_docs_connection_change(name)
            
            after = [card["url"] for card in app.docs_cards]
            
            assert before != after
            assert any(f"/c/{name}/tables" in link for link in after)
        finally:
            if created:
                config.remove_connection(name)
            app._refresh_api_docs()

    def test_switching_to_default_uses_short_paths(self, app):
        """Для подключения по умолчанию показывается короткая форма пути."""
        from src.config import config

        app.docs_connection_var.set(config.default_connection)
        app._on_docs_connection_change(config.default_connection)
        
        urls = [card["url"] for card in app.docs_cards]
        
        assert any(url.endswith("/api/v1/tables") for url in urls)

    def test_switcher_updates_after_adding_connection(self, app):
        """После добавления подключения оно появляется в переключателе."""
        from src.config import config

        name = "ВтороеПодключение"
        created = False
        
        if config.get_connection(name) is None:
            config.add_connection(name)
            created = True
        
        try:
            app._reload_runtime_config()
            
            assert name in app.docs_connection_menu.cget("values")
        finally:
            if created:
                config.remove_connection(name)
            app._reload_runtime_config()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

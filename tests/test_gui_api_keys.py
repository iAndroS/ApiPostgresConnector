"""Тесты управления API-ключами: раздельность по подключениям, копирование, изменение."""
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


@pytest.fixture
def two_connections(app, isolated_config):
    """Готовит два подключения с разными ключами."""
    from src.config import config

    names = []
    for name in ("КлючиA", "КлючиB"):
        if config.get_connection(name) is None:
            config.add_connection(name, api_keys=[f"key-{name}"])
            names.append(name)
    
    app._refresh_connections_tree()
    app._refresh_api_docs()
    
    yield names
    
    for name in names:
        config.remove_connection(name)
    
    app._refresh_connections_tree()
    app._refresh_api_docs()


class TestApiKeyField:
    """Проверка поля основного ключа."""

    def test_field_shows_primary_key(self, app, two_connections):
        """В поле показан первый (основной) ключ выбранного подключения."""
        app._load_connection_into_editor("КлючиA")
        
        assert app.entry_api_key.get() == "key-КлючиA"
    
    def test_switching_connection_changes_key(self, app, two_connections):
        """При переключении подключения показывается его ключ."""
        app._load_connection_into_editor("КлючиA")
        app._load_connection_into_editor("КлючиB")
        
        assert app.entry_api_key.get() == "key-КлючиB"
    
    def test_list_contains_all_keys(self, app, two_connections):
        """Список содержит все ключи подключения."""
        app._load_connection_into_editor("КлючиA")
        
        keys = list(app.keys_listbox.get(0, "end"))
        
        assert "key-КлючиA" in keys


class TestApiKeyActions:
    """Проверка действий с ключами."""

    def test_copy_primary_key(self, app, two_connections):
        """Кнопка копирования копирует основной ключ в буфер."""
        import pyperclip
        
        app._load_connection_into_editor("КлючиA")
        pyperclip.copy("")
        
        app._copy_api_key()
        
        assert pyperclip.paste() == "key-КлючиA"

    def test_save_new_primary_key(self, app, two_connections):
        """Изменённый ключ сохраняется и применяется к подключению."""
        from src.config import config
        
        app._load_connection_into_editor("КлючиA")
        
        app.entry_api_key.delete(0, "end")
        app.entry_api_key.insert(0, "new-primary-key")
        app._save_api_key()
        
        connection = config.get_connection("КлючиA")
        assert connection["api_keys"][0] == "new-primary-key"
        
        # В списке ключ тоже обновился
        keys = list(app.keys_listbox.get(0, "end"))
        assert keys[0] == "new-primary-key"

    def test_generated_key_becomes_primary(self, app, two_connections):
        """Сгенерированный ключ становится основным."""
        from src.config import config
        
        app._load_connection_into_editor("КлючиA")
        app._generate_api_key()
        
        connection = config.get_connection("КлючиA")
        generated = connection["api_keys"][0]
        
        assert generated != "key-КлючиA"
        assert app.entry_api_key.get() == generated

    def test_keys_are_separate_per_connection(self, app, two_connections):
        """Ключи одного подключения не действуют в другом."""
        from src.config import config
        
        app._load_connection_into_editor("КлючиA")
        app.entry_api_key.delete(0, "end")
        app.entry_api_key.insert(0, "only-for-a")
        app._save_api_key()
        
        app._load_connection_into_editor("КлючиB")
        
        assert app.entry_api_key.get() == "key-КлючиB"
        assert "only-for-a" not in config.get_connection("КлючиB")["api_keys"]

    def test_remove_last_key_is_forbidden(self, app, two_connections):
        """Последний ключ удалить нельзя."""
        from src.config import config
        
        app._load_connection_into_editor("КлючиA")
        app.keys_listbox.selection_set(0)
        
        app._remove_api_key()
        
        assert config.get_connection("КлючиA")["api_keys"] == ["key-КлючиA"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

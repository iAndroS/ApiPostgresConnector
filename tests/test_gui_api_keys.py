"""Тесты вкладки «Подключения»: единый API-ключ, статус, скрытая форма, вкл/выкл."""
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

    app._refresh_connections_table()

    yield names

    for name in names:
        config.remove_connection(name)

    app._refresh_connections_table()


class TestSingleApiKey:
    """У подключения один API-ключ: генерация и копирование."""

    def test_generated_key_replaces_previous(self, app, two_connections):
        """Генерация заменяет ключ — у подключения остаётся один ключ."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._update_selected_connection()

        app._generate_api_key()

        keys = config.get_connection("КлючиA")["api_keys"]

        assert len(keys) == 1
        assert keys[0] != "key-КлючиA"

    def test_copy_selected_key(self, app, two_connections):
        """Кнопка копирования копирует ключ выбранного подключения."""
        import pyperclip

        app._current_connection = "КлючиA"
        app._update_selected_connection()
        pyperclip.copy("")

        app._copy_api_key()

        assert pyperclip.paste() == "key-КлючиA"

    def test_copy_key_by_row_icon(self, app, two_connections):
        """Клик по иконке в строке копирует ключ этого подключения."""
        import pyperclip

        pyperclip.copy("")

        app._copy_connection_key("КлючиB")

        assert pyperclip.paste() == "key-КлючиB"

    def test_key_label_shows_masked_key(self, app, two_connections):
        """В подписи ключ показан в маскированном виде."""
        app._current_connection = "КлючиA"
        app._update_selected_connection()

        text = app.lbl_selected_key.cget("text")

        assert "key-КлючиA" not in text
        assert text.startswith("Ключ: ")

    def test_long_key_is_masked_with_ellipsis(self, app):
        """Длинный ключ показывается в виде «начало…конец»."""
        from src.gui.main_window import MainWindow

        masked = MainWindow._mask_key("abcdefghijklmnop")

        assert masked.startswith("abcdef")
        assert masked.endswith("mnop")
        assert "abcdefghijklmnop" not in masked

    def test_keys_are_separate_per_connection(self, app, two_connections):
        """Ключ одного подключения не действует в другом."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._generate_api_key()

        new_key = config.get_connection("КлючиA")["api_keys"][0]

        assert config.get_connection("КлючиB")["api_keys"] == ["key-КлючиB"]
        assert new_key not in config.get_connection("КлючиB")["api_keys"]


class TestConnectionsTable:
    """Таблица подключений: строки, статус, выделение."""

    def test_table_contains_all_connections(self, app, two_connections):
        """В таблице есть все подключения."""
        names = [row["name"] for row in app.table_connections.get_rows()]

        assert "КлючиA" in names
        assert "КлючиB" in names

    def test_row_has_status_and_key_flag(self, app, two_connections):
        """В строке есть статус подключения и признак наличия ключа."""
        rows = {row["name"]: row for row in app.table_connections.get_rows()}

        row = rows["КлючиA"]

        assert row["status_color"]
        assert row["status_text"]
        assert row["has_key"] is True

    def test_default_connection_is_marked(self, app, two_connections):
        """Подключение по умолчанию помечено в таблице."""
        from src.config import config

        rows = {row["name"]: row for row in app.table_connections.get_rows()}

        assert rows[config.default_connection]["is_default"] is True

    def test_disabled_connection_has_own_status(self, app, two_connections):
        """Отключённое подключение отмечено в статусе."""
        from src.config import config

        config.set_connection_enabled("КлючиA", False)
        app._refresh_connections_table()

        rows = {row["name"]: row for row in app.table_connections.get_rows()}

        assert rows["КлючиA"]["status_text"] == "выключено"

    def test_select_connection_updates_key_label(self, app, two_connections):
        """Выбор строки показывает ключ выбранного подключения."""
        app._on_connection_select("КлючиB")

        assert app._current_connection == "КлючиB"
        assert app.table_connections.get_selected() == "КлючиB"


class TestConnectionEditor:
    """Форма параметров подключения показывается только при создании/редактировании."""

    def test_editor_is_hidden_by_default(self, app):
        """Форма параметров изначально скрыта."""
        assert app._is_editor_visible() is False

    def test_edit_button_shows_editor(self, app, two_connections):
        """Кнопка «Изменить» открывает форму с данными подключения."""
        app._current_connection = "КлючиA"

        app._edit_connection()

        assert app._is_editor_visible() is True
        assert "КлючиA" in app.lbl_editor_title.cget("text")

    def test_save_keeps_edited_values(self, app, two_connections):
        """Сохранение формы записывает изменённые параметры в конфиг."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._edit_connection()

        app.entry_host.delete(0, "end")
        app.entry_host.insert(0, "test-host")
        app._save_connection()

        assert config.get_connection("КлючиA")["database"]["host"] == "test-host"
        assert app._is_editor_visible() is False

    def test_hidden_editor_does_not_overwrite_settings(self, app, two_connections):
        """Скрытая форма не перетирает параметры подключения."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._edit_connection()

        app.entry_host.delete(0, "end")
        app.entry_host.insert(0, "test-host")
        app._hide_editor()

        app._save_settings()

        assert config.get_connection("КлючиA")["database"]["host"] != "test-host"


class TestConnectionToggle:
    """Переключатель вкл/выкл подключения."""

    def test_switch_reflects_config(self, app, two_connections):
        """Переключатель показывает состояние подключения."""
        from src.config import config

        config.set_connection_enabled("КлючиA", False)
        app._current_connection = "КлючиA"
        app._update_selected_connection()

        assert not app.switch_enabled.get()

        config.set_connection_enabled("КлючиA", True)
        app._update_selected_connection()

        assert app.switch_enabled.get()

    def test_toggle_saves_state(self, app, two_connections):
        """Переключение сохраняется в конфиг."""
        from src.config import config

        app._current_connection = "КлючиA"
        app.switch_enabled.deselect()

        app._on_toggle_enabled()

        assert config.is_connection_enabled("КлючиA") is False

        app.switch_enabled.select()
        app._on_toggle_enabled()

        assert config.is_connection_enabled("КлючиA") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

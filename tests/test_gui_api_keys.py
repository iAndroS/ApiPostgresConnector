"""Тесты вкладки «Подключения»: единый API-ключ, статус, скрытая форма, иконки строк."""
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


def _patch_clipboard(monkeypatch):
    """Подменяет буфер обмена — список скопированных значений."""
    import pyperclip

    copied = []
    monkeypatch.setattr(pyperclip, "copy", lambda text: copied.append(text))
    return copied


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

        app._regenerate_connection_key("КлючиA")

        keys = config.get_connection("КлючиA")["api_keys"]

        assert len(keys) == 1
        assert keys[0] != "key-КлючиA"

    def test_copy_selected_key(self, app, two_connections, monkeypatch):
        """Иконка копирования копирует ключ выбранного подключения."""
        copied = _patch_clipboard(monkeypatch)

        app._copy_connection_key("КлючиA")

        assert copied == ["key-КлючиA"]

    def test_copy_key_by_row_icon(self, app, two_connections, monkeypatch):
        """Клик по иконке в строке копирует ключ этого подключения."""
        copied = _patch_clipboard(monkeypatch)

        app._copy_connection_key("КлючиB")

        assert copied == ["key-КлючиB"]

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

        app._regenerate_connection_key("КлючиA")

        new_key = config.get_connection("КлючиA")["api_keys"][0]

        assert config.get_connection("КлючиB")["api_keys"] == ["key-КлючиB"]
        assert new_key not in config.get_connection("КлючиB")["api_keys"]


class TestConnectionsTable:
    """Таблица подключений: строки, статус, иконки."""

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

    def test_disabled_connection_has_own_status(self, app, two_connections):
        """Отключённое подключение отмечено в статусе."""
        from src.config import config

        config.set_connection_enabled("КлючиA", False)
        app._refresh_connections_table()

        rows = {row["name"]: row for row in app.table_connections.get_rows()}

        assert rows["КлючиA"]["status_text"] == "выключено"

    def test_row_keeps_enabled_flag(self, app, two_connections):
        """В строке есть признак включённого подключения (для иконки-переключателя)."""
        from src.config import config

        config.set_connection_enabled("КлючиA", False)
        app._refresh_connections_table()

        rows = {row["name"]: row for row in app.table_connections.get_rows()}

        assert rows["КлючиA"]["enabled"] is False
        assert rows["КлючиB"]["enabled"] is True

    def test_select_connection_updates_selection(self, app, two_connections):
        """Выбор строки запоминается в таблице."""
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

    def test_name_field_renames_connection(self, app, two_connections):
        """Название в форме переименовывает подключение."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._edit_connection()

        app.entry_name.delete(0, "end")
        app.entry_name.insert(0, "Переименовано")
        app._save_connection()

        assert config.get_connection("Переименовано") is not None
        assert config.get_connection("КлючиA") is None
        assert app._current_connection == "Переименовано"

    def test_duplicate_name_is_rejected(self, app, two_connections):
        """Новое название не должно совпадать с существующим подключением."""
        from src.config import config

        app._current_connection = "КлючиA"
        app._edit_connection()

        app.entry_name.delete(0, "end")
        app.entry_name.insert(0, "КлючиB")
        app._save_connection()

        assert config.get_connection("КлючиA") is not None
        assert app._current_connection == "КлючиA"

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


class TestConnectionActions:
    """Действия с подключениями: добавить, дублировать, удалить."""

    def test_add_connection_creates_connection(self, app, isolated_config, monkeypatch):
        """«Добавить» создаёт подключение с ключом и открывает форму."""
        from src.config import config

        monkeypatch.setattr(app, "_prompt_text", lambda *a, **kw: "НовоеПодключение")

        app._add_connection()

        connection = config.get_connection("НовоеПодключение")

        assert connection is not None
        assert connection["api_keys"]
        assert app._current_connection == "НовоеПодключение"
        assert app._is_editor_visible() is True

        config.remove_connection("НовоеПодключение")

    def test_duplicate_connection_copies_params(self, app, two_connections, monkeypatch):
        """«Дублировать» создаёт копию с теми же параметрами БД."""
        from src.config import config

        monkeypatch.setattr(app, "_prompt_text", lambda *a, **kw: "Копия")

        app._current_connection = "КлючиA"
        app._duplicate_connection()

        copy = config.get_connection("Копия")
        source = config.get_connection("КлючиA")

        assert copy is not None
        assert copy["database"] == source["database"]
        assert copy["api_keys"] == source["api_keys"]

        config.remove_connection("Копия")

    def test_remove_connection(self, app, two_connections, monkeypatch):
        """«Удалить» удаляет подключение после подтверждения."""
        from src.config import config

        monkeypatch.setattr(app, "_ask_confirmation", lambda *a, **kw: True)

        app._current_connection = "КлючиB"
        app._remove_connection()

        assert config.get_connection("КлючиB") is None

    def test_prompt_dialog_opens_and_closes(self, app):
        """Модальный диалог ввода открывается и закрывается без ошибок."""
        import customtkinter as ctk

        app.update()

        def close_dialog():
            for widget in app.winfo_children():
                if isinstance(widget, ctk.CTkToplevel):
                    widget.destroy()

        app.after(200, close_dialog)

        assert app._prompt_text("Тест", "Введите текст:") is None


class TestConnectionToggle:
    """Переключатель вкл/выкл подключения (иконка в строке)."""

    def test_toggle_saves_state(self, app, two_connections):
        """Клик по иконке переключает состояние подключения."""
        from src.config import config

        app._toggle_connection("КлючиA")

        assert config.is_connection_enabled("КлючиA") is False

        app._toggle_connection("КлючиA")

        assert config.is_connection_enabled("КлючиA") is True

    def test_api_status_counts_only_enabled(self, app, two_connections):
        """В статусе API считаются только включённые подключения."""
        from src.config import config

        config.set_connection_enabled("КлючиA", False)

        total = len(config.connections)
        enabled = len([c for c in config.connections if c.get("enabled", True)])
        text = app._api_status_text()

        assert f"{enabled} из {total}" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

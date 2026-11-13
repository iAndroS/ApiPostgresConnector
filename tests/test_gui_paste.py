"""Тесты вставки из буфера обмена (Ctrl+V) в текстовые поля GUI.

Тест создаёт окно Tk, поэтому при отсутствии графического окружения он
пропускается (pytest.skip), а не падает.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class FakeEvent:
    """Имитация Tk-события для прямого вызова обработчика."""

    def __init__(self, widget):
        self.widget = widget


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


def paste(app, entry, text: str):
    """Кладёт текст в буфер и вызывает обработчик вставки.

    Args:
        app: Окно приложения
        entry: CTkEntry или tk.Entry
        text: Текст для вставки
    """
    import pyperclip

    pyperclip.copy(text)

    target = getattr(entry, "_entry", entry)
    app._on_paste(FakeEvent(target))


class TestPasteBinding:
    """Проверка регистрации привязок вставки."""

    def test_binding_registered_on_internal_entry(self, app):
        """Ctrl+V привязан к внутреннему tk.Entry каждого поля."""
        for entry in (app.entry_host, app.entry_port, app.entry_user, app.entry_password):
            target = getattr(entry, "_entry", entry)
            assert target.bind("<Control-v>"), f"Нет привязки Ctrl+V: {entry}"
            assert target.bind("<Control-V>"), f"Нет привязки Ctrl+Shift+V: {entry}"

    def test_no_global_binding(self, app):
        """Глобальной привязки нет — она вставляла текст второй раз."""
        assert not app.bind_all("<Control-v>")
        assert not app.bind_all("<Control-V>")

    def test_api_tab_fields_registered(self, app):
        """Привязка есть и у полей вкладки «API»."""
        for entry in (app.entry_api_host, app.entry_api_port):
            target = getattr(entry, "_entry", entry)
            assert target.bind("<Control-v>")


class TestPaste:
    """Проверка вставки из буфера обмена."""

    def test_paste_inserts_text_once(self, app):
        """Текст вставляется ровно один раз (регрессия: было дважды)."""
        entry = app.entry_host
        entry.delete(0, "end")

        paste(app, entry, "127.0.0.1")

        assert entry.get() == "127.0.0.1"

    def test_paste_into_empty_field(self, app):
        """Вставка в пустое поле даёт ровно скопированный текст."""
        entry = app.entry_dbname
        entry.delete(0, "end")

        paste(app, entry, "crm")

        assert entry.get() == "crm"

    def test_paste_inserts_at_cursor(self, app):
        """Вставка идёт в позицию курсора, а не в конец."""
        entry = app.entry_user
        entry.delete(0, "end")
        entry.insert(0, "user")
        entry.icursor(0)

        paste(app, entry, "new")

        assert entry.get() == "newuser"

    def test_paste_replaces_selection(self, app):
        """Выделенный текст заменяется вставленным."""
        entry = app.entry_port
        entry.delete(0, "end")
        entry.insert(0, "5432")
        entry.select_range(0, 4)

        paste(app, entry, "5000")

        assert entry.get() == "5000"

    def test_paste_works_in_all_connection_fields(self, app):
        """Вставка работает во всех полях подключения."""
        fields = [
            app.entry_dsn,
            app.entry_host,
            app.entry_port,
            app.entry_dbname,
            app.entry_user,
            app.entry_password,
        ]

        for index, entry in enumerate(fields):
            entry.delete(0, "end")
            paste(app, entry, f"value{index}")
            assert entry.get() == f"value{index}", f"Поле {index}: {entry.get()!r}"

    def test_paste_with_empty_clipboard_does_nothing(self, app):
        """Пустой буфер не изменяет содержимое поля."""
        import pyperclip

        pyperclip.copy("")

        entry = app.entry_host
        entry.delete(0, "end")
        entry.insert(0, "unchanged")

        paste(app, entry, "")

        assert entry.get() == "unchanged"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

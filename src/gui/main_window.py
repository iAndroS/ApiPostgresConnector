"""Main GUI window for ApiPostgresConnector."""
import logging
import threading
import webbrowser
from datetime import datetime
from typing import Optional, Any, List
from urllib.parse import quote

import tkinter as tk
import customtkinter as ctk

# Pyperclip for clipboard operations (with PyInstaller compatibility)
try:
    import pyperclip
except ImportError:
    pyperclip = None

# System tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    PYTRAY_AVAILABLE = True
except ImportError:
    PYTRAY_AVAILABLE = False

from ..config import config
from ..api.routes import get_registry
from ..version import VERSION_STRING
from .connection_table import ConnectionTable

logger = logging.getLogger(__name__)

# Global variable for tray icon
_tray_icon: Optional[Any] = None
_last_activity_time: Optional[datetime] = None


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self, api_server: Optional[object] = None):
        super().__init__()

        self.api_server = api_server
        self._current_connection: Optional[str] = None
        self._editor_connection: Optional[str] = None
        self._editor_visible = False
        self.docs_cards: List[dict] = []

        # Configure window
        gui_config = config.gui
        self.title(VERSION_STRING)
        
        # Минимальный размер — чтобы вкладка «Подключения» помещалась
        width = max(int(gui_config.get('width', 700) or 700), 700)
        height = max(int(gui_config.get('height', 700) or 700), 700)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)

        # Set theme
        theme = gui_config.get("theme", "dark-blue")
        ctk.set_appearance_mode("dark" if "dark" in theme else "light")
        ctk.set_default_color_theme("blue")

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create UI
        self._create_header()
        self._create_tabs()
        self._create_footer()

        # API status update
        self.after(2000, self._update_api_status)
        
        # Bind minimize to tray event
        self.bind("<Unmap>", lambda e: self._minimize_to_tray())
        
        # NOTE: вставка из буфера обмена (Ctrl+V) включается отдельно
        # для каждого текстового поля — см. _register_paste()
        
        # Перехват события закрытия окна (крестик)
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

    def _create_header(self):
        """Create header section."""
        self.header_frame = ctk.CTkFrame(self, height=60)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Logo/Title
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=VERSION_STRING,
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=10)

        # API Status indicator
        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="API: Не запущен",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=0, column=2, padx=20, pady=10)

    def _create_tabs(self):
        """Create tab view."""
        self.tabview = ctk.CTkTabview(self, width=660, height=520)
        self.tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Connections tab (databases + API keys)
        self.tab_connections = self.tabview.add("Подключения")
        self._create_connections_tab()

        # API tab (global server settings)
        self.tab_api = self.tabview.add("API")
        self._create_api_tab()

        # API Documentation tab
        self.tab_api_docs = self.tabview.add("Документация API")
        self._create_api_docs_tab()

    # ------------------------------------------------------------------
    # Вкладка «Подключения»
    # ------------------------------------------------------------------

    def _create_connections_tab(self):
        """Создаёт вкладку «Подключения»: таблица, панель управления, скрытая форма параметров."""
        container = ctk.CTkScrollableFrame(self.tab_connections)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # --- Таблица подключений ---
        self.table_connections = ConnectionTable(
            container,
            visible_rows=4,
            on_select=self._on_connection_select,
            on_copy_key=self._copy_connection_key,
        )
        self.table_connections.pack(fill="x", padx=4, pady=(4, 0))

        ctk.CTkLabel(
            container,
            text="Иконка в колонке «Ключ» — скопировать ключ подключения",
            text_color="gray",
            anchor="w",
            font=ctk.CTkFont(size=9)
        ).pack(fill="x", padx=4)

        # --- Кнопки управления подключениями ---
        buttons_frame = ctk.CTkFrame(container, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=4, pady=4)

        ctk.CTkButton(buttons_frame, text="Добавить", width=70,
                      command=self._add_connection).pack(side="left", padx=1)
        ctk.CTkButton(buttons_frame, text="Изменить", width=70,
                      command=self._edit_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Переименовать", width=85,
                      command=self._rename_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Дублировать", width=80,
                      command=self._duplicate_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Удалить", width=65,
                      command=self._remove_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="По умолчанию", width=90,
                      command=self._set_default_connection).pack(side="left", padx=2)

        # --- Выбранное подключение: вкл/выкл и API-ключ ---
        selected_frame = ctk.CTkFrame(container, fg_color="transparent")
        selected_frame.pack(fill="x", padx=4, pady=(2, 2))

        self.switch_enabled = ctk.CTkSwitch(
            selected_frame,
            text="Подключение включено",
            width=170,
            command=self._on_toggle_enabled
        )
        self.switch_enabled.pack(side="left", padx=(0, 8))

        self.lbl_selected_key = ctk.CTkLabel(selected_frame, text="Ключ: —", anchor="w")
        self.lbl_selected_key.pack(side="left", padx=(0, 8))

        self.btn_generate_key = ctk.CTkButton(selected_frame, text="Сгенерировать ключ", width=140,
                                              command=self._generate_api_key)
        self.btn_generate_key.pack(side="left", padx=2)

        self.btn_copy_key = ctk.CTkButton(selected_frame, text="Копировать ключ", width=120,
                                          command=self._copy_api_key)
        self.btn_copy_key.pack(side="left", padx=2)

        # --- Статус (виден всегда, независимо от формы параметров) ---
        self.lbl_connection_status = ctk.CTkLabel(container, text="", anchor="w")
        self.lbl_connection_status.pack(fill="x", padx=4, pady=(2, 0))

        self.lbl_db_state = ctk.CTkLabel(container, text="", anchor="w")
        self.lbl_db_state.pack(fill="x", padx=4, pady=(0, 4))

        # --- Форма параметров подключения (показывается только при создании/редактировании) ---
        self.editor_frame = ctk.CTkFrame(
            container, fg_color="transparent", border_width=1, border_color="#3a3a3a"
        )
        editor = self.editor_frame
        editor.grid_columnconfigure(1, weight=1)

        self.lbl_editor_title = ctk.CTkLabel(editor, text="Параметры подключения", anchor="w",
                                              font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_editor_title.grid(row=0, column=0, columnspan=3, padx=4, pady=(6, 2), sticky="w")

        # DSN
        ctk.CTkLabel(editor, text="DSN:").grid(row=1, column=0, padx=4, pady=2, sticky="w")
        self.entry_dsn = ctk.CTkEntry(editor, width=240)
        self.entry_dsn.grid(row=1, column=1, padx=4, pady=2, sticky="ew")
        ctk.CTkButton(editor, text="Из DSN", width=70,
                      command=self._parse_dsn).grid(row=1, column=2, padx=4, pady=2)

        # Host
        ctk.CTkLabel(editor, text="Хост:").grid(row=2, column=0, padx=4, pady=2, sticky="w")
        self.entry_host = ctk.CTkEntry(editor, width=240)
        self.entry_host.grid(row=2, column=1, padx=4, pady=2, sticky="ew")

        # Port
        ctk.CTkLabel(editor, text="Порт:").grid(row=3, column=0, padx=4, pady=2, sticky="w")
        self.entry_port = ctk.CTkEntry(editor, width=240)
        self.entry_port.grid(row=3, column=1, padx=4, pady=2, sticky="ew")

        # Database name
        ctk.CTkLabel(editor, text="База данных:").grid(row=4, column=0, padx=4, pady=2, sticky="w")
        self.entry_dbname = ctk.CTkEntry(editor, width=240)
        self.entry_dbname.grid(row=4, column=1, padx=4, pady=2, sticky="ew")

        # User
        ctk.CTkLabel(editor, text="Пользователь:").grid(row=5, column=0, padx=4, pady=2, sticky="w")
        self.entry_user = ctk.CTkEntry(editor, width=240)
        self.entry_user.grid(row=5, column=1, padx=4, pady=2, sticky="ew")

        # Password
        ctk.CTkLabel(editor, text="Пароль:").grid(row=6, column=0, padx=4, pady=2, sticky="w")
        self.entry_password = ctk.CTkEntry(editor, width=240, show="*")
        self.entry_password.grid(row=6, column=1, padx=4, pady=2, sticky="ew")

        editor_buttons = ctk.CTkFrame(editor, fg_color="transparent")
        editor_buttons.grid(row=7, column=0, columnspan=3, padx=4, pady=(6, 4), sticky="w")

        self.btn_test = ctk.CTkButton(
            editor_buttons, text="Проверить подключение", width=160, command=self._test_connection
        )
        self.btn_test.pack(side="left", padx=1)

        self.btn_save_connection = ctk.CTkButton(
            editor_buttons, text="Сохранить", width=95, command=self._save_connection
        )
        self.btn_save_connection.pack(side="left", padx=2)

        self.btn_hide_editor = ctk.CTkButton(
            editor_buttons, text="Скрыть", width=85, command=self._hide_editor
        )
        self.btn_hide_editor.pack(side="left", padx=2)

        # Right-click paste menu for all entry fields
        self._setup_paste_functionality()

        # Заполняем таблицу после создания всех виджетов
        self._refresh_connections_table()

    # ------------------------------------------------------------------
    # Таблица подключений
    # ------------------------------------------------------------------

    def _refresh_connections_table(self):
        """Перерисовывает таблицу подключений (данные + статус)."""
        if not hasattr(self, "table_connections"):
            return

        self.table_connections.set_rows(self._build_connection_rows())

        # При первом запуске выделяем подключение по умолчанию
        if not self._current_connection:
            default_name = config.default_connection
            if default_name:
                self._current_connection = default_name

        if self._current_connection:
            self.table_connections.select(self._current_connection)
            self._update_selected_connection()

    def _build_connection_rows(self) -> List[dict]:
        """Собирает строки таблицы: данные подключения и состояние соединения."""
        registry = get_registry()
        default_name = config.default_connection
        rows = []

        for connection in config.connections:
            db = connection.get("database", {})
            name = connection.get("name", "")
            enabled = bool(connection.get("enabled", True))
            status_color, status_text = self._connection_status(name, enabled, registry)

            rows.append({
                "name": name,
                "host": db.get("host", ""),
                "port": db.get("port", ""),
                "db": db.get("database", ""),
                "user": db.get("user", ""),
                "status_color": status_color,
                "status_text": status_text,
                "has_key": bool(connection.get("api_keys")),
                "is_default": name == default_name,
            })

        return rows

    def _connection_status(self, name: str, enabled: bool, registry) -> tuple:
        """Определяет статус подключения: цвет точки и подпись.

        Returns:
            tuple (цвет, подпись)
        """
        if not enabled:
            return "#7a7a7a", "выключено"

        profile = registry.get(name) if registry else None

        if profile is None:
            return "#7a7a7a", "—"

        if not profile.is_db_created:
            return "#e0a800", "проверка"

        if profile.db.is_connected():
            return "#3fae4f", "подключено"

        return "#e04f4f", "ошибка"

    def _update_connection_status(self):
        """Обновляет только статус подключений (вызывается каждые 2 секунды)."""
        if not hasattr(self, "table_connections"):
            return

        self.table_connections.set_rows(self._build_connection_rows())

    def _on_connection_select(self, name: str):
        """Выбор подключения в таблице."""
        if name == self._current_connection:
            self._update_selected_connection()
            return

        # Открытая форма — правки предыдущего подключения сохраняем
        if self._is_editor_visible() and self._current_connection:
            self._apply_editor_to_connection()

        self._current_connection = name
        self.table_connections.select(name)
        self._update_selected_connection()

        if self._is_editor_visible():
            self._load_connection_into_editor(name)

    def _update_selected_connection(self):
        """Обновляет переключатель вкл/выкл и подпись с ключом."""
        name = self._current_connection
        connection = config.get_connection(name) if name else None

        if not connection:
            self.switch_enabled.deselect()
            self.lbl_selected_key.configure(text="Ключ: —")
            self.btn_generate_key.configure(state="disabled")
            self.btn_copy_key.configure(state="disabled")
            return

        if config.is_connection_enabled(name):
            self.switch_enabled.select()
        else:
            self.switch_enabled.deselect()

        api_keys = connection.get("api_keys") or []
        self.lbl_selected_key.configure(text=f"Ключ: {self._mask_key(api_keys[0])}")

        self.btn_generate_key.configure(state="normal")
        self.btn_copy_key.configure(state="normal" if api_keys else "disabled")

    @staticmethod
    def _mask_key(key: str) -> str:
        """Маскирует ключ для показа в интерфейсе."""
        if not key:
            return "не задан"
        if len(key) <= 12:
            return "•" * len(key)
        return f"{key[:6]}…{key[-4:]}"

    # ------------------------------------------------------------------
    # Форма параметров подключения
    # ------------------------------------------------------------------

    def _is_editor_visible(self) -> bool:
        """True если форма параметров подключения показана."""
        return self._editor_visible

    def _show_editor(self):
        """Показывает форму параметров подключения."""
        if not hasattr(self, "editor_frame"):
            return

        if not self._editor_visible:
            self._editor_visible = True
            self.editor_frame.pack(fill="x", padx=4, pady=(6, 4))

    def _hide_editor(self):
        """Скрывает форму параметров подключения (несохранённые правки отбрасываются)."""
        if not hasattr(self, "editor_frame"):
            return

        if self._editor_visible:
            self._editor_visible = False
            self.editor_frame.pack_forget()

        self._editor_connection = None
        self.lbl_editor_title.configure(text="Параметры подключения")

    def _edit_connection(self):
        """Открывает форму параметров выбранного подключения."""
        name = self._current_connection

        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return

        self._load_connection_into_editor(name)
        self._show_editor()

        self.lbl_connection_status.configure(
            text=f"Редактирование подключения «{name}»", text_color="gray")

    def _save_connection(self):
        """Сохраняет параметры подключения из формы и закрывает её."""
        name = self._current_connection

        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return

        if not self._apply_editor_to_connection():
            return

        config.save()
        self._reload_runtime_config()
        self._hide_editor()

        self.lbl_connection_status.configure(
            text=f"Параметры подключения «{name}» сохранены", text_color="green")

    def _on_toggle_enabled(self):
        """Включает или отключает выбранное подключение."""
        name = self._current_connection

        if not name:
            self.switch_enabled.deselect()
            return

        enabled = bool(self.switch_enabled.get())
        config.set_connection_enabled(name, enabled)
        config.save()
        self._reload_runtime_config()

        state = "включено" if enabled else "выключено"
        self.lbl_connection_status.configure(
            text=f"Подключение «{name}» {state}", text_color="green" if enabled else "orange")

    def _load_connection_into_editor(self, name: str):
        """Заполняет поля формы данными подключения."""
        connection = config.get_connection(name)
        if not connection:
            return

        db = connection.get("database", {})
        self._current_connection = name
        self._editor_connection = name

        self.entry_dsn.delete(0, "end")
        self.entry_host.delete(0, "end")
        self.entry_host.insert(0, db.get("host", ""))
        self.entry_port.delete(0, "end")
        self.entry_port.insert(0, str(db.get("port", 5432)))
        self.entry_dbname.delete(0, "end")
        self.entry_dbname.insert(0, db.get("database", ""))
        self.entry_user.delete(0, "end")
        self.entry_user.insert(0, db.get("user", ""))
        self.entry_password.delete(0, "end")
        self.entry_password.insert(0, db.get("password", ""))

        self.lbl_editor_title.configure(text=f"Параметры подключения «{name}»")
        self.lbl_connection_status.configure(text=f"Подключение: {name}", text_color="gray")

    def _apply_editor_to_connection(self) -> bool:
        """Переносит значения из полей формы в конфиг выбранного подключения.

        Returns:
            bool: True если значения применены, False при ошибке валидации
        """
        name = self._current_connection
        if not name:
            return True
        
        # Форма не загружена для этого подключения — сохранять нечего
        if not self._editor_connection or self._editor_connection != name:
            return True
        
        connection = config.get_connection(name)
        if not connection:
            return True
        
        port_text = self.entry_port.get().strip()
        if not port_text.isdigit():
            self.lbl_connection_status.configure(
                text=f"Внимание:  Порт подключения должен быть числом (получено: '{port_text}')",
                text_color="orange"
            )
            return False
        
        connection.setdefault("database", {}).update({
            "host": self.entry_host.get().strip(),
            "port": int(port_text),
            "database": self.entry_dbname.get().strip(),
            "user": self.entry_user.get().strip(),
            "password": self.entry_password.get()
        })
        
        return True
    
    # ------------------------------------------------------------------
    # Управление подключениями
    # ------------------------------------------------------------------

    def _add_connection(self):
        """Создаёт новое подключение и открывает форму параметров."""
        name = self._prompt_text("Новое подключение", "Название подключения:")
        
        if not name:
            return
        
        try:
            config.add_connection(name)
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"Внимание: {e}", text_color="orange")
            return
        
        # Новому подключению сразу генерируем API-ключ
        try:
            config.ensure_api_key(name)
        except Exception as e:
            logger.warning(f"Failed to generate API key for '{name}': {e}")
        
        config.save()
        self._current_connection = name
        self._refresh_connections_table()
        self._update_selected_connection()
        self._reload_runtime_config()
        self._load_connection_into_editor(name)
        self._show_editor()
        self.lbl_connection_status.configure(text=f"Создано подключение '{name}'", text_color="green")
    
    def _rename_connection(self):
        """Переименовывает выбранное подключение."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        new_name = self._prompt_text("Переименование", "Новое название:", initial_value=name)
        
        if not new_name or new_name == name:
            return
        
        try:
            config.rename_connection(name, new_name)
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"Внимание: {e}", text_color="orange")
            return
        
        self._current_connection = new_name
        config.save()
        self._refresh_connections_table()
        self._update_selected_connection()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"Подключение переименовано в '{new_name}'", text_color="green")
    
    def _duplicate_connection(self):
        """Создаёт копию выбранного подключения."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        new_name = self._prompt_text("Дублирование", "Название копии:", initial_value=f"{name}-copy")
        
        if not new_name:
            return
        
        source = config.get_connection(name)
        
        try:
            config.add_connection(
                new_name,
                database=dict(source.get("database", {})),
                api_keys=list(source.get("api_keys", [])),
                enabled=bool(source.get("enabled", True))
            )
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"Внимание: {e}", text_color="orange")
            return
        
        config.save()
        self._current_connection = new_name
        self._refresh_connections_table()
        self._update_selected_connection()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"Создана копия '{new_name}'", text_color="green")
    
    def _remove_connection(self):
        """Удаляет выбранное подключение."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        if not self._ask_confirmation(f"Удалить подключение '{name}'?"):
            return
        
        if not config.remove_connection(name):
            self.lbl_connection_status.configure(
                text="Внимание: нельзя удалить последнее подключение", text_color="orange")
            return
        
        self._current_connection = None
        self._hide_editor()
        config.save()
        self._refresh_connections_table()
        self._update_selected_connection()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(text=f"Подключение '{name}' удалено", text_color="green")
    
    def _set_default_connection(self):
        """Назначает выбранное подключение подключением по умолчанию."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        try:
            config.set_default_connection(name)
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"Внимание: {e}", text_color="orange")
            return
        
        config.save()
        self._refresh_connections_table()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"Подключением по умолчанию назначено '{name}'", text_color="green")
    
    def _ask_confirmation(self, message: str) -> bool:
        """Показывает диалог подтверждения."""
        from tkinter import messagebox
        return messagebox.askyesno("Подтверждение", message, parent=self)
    
    def _prompt_text(self, title: str, prompt: str, initial_value: str = "") -> Optional[str]:
        """Модальный диалог ввода строки в стиле приложения.

        Args:
            title: Заголовок окна
            prompt: Подпись над полем ввода
            initial_value: Начальное значение поля

        Returns:
            Введённый текст (без пробелов по краям) или None, если ввод отменён
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.transient(self)
        
        width, height = 420, 160
        
        ctk.CTkLabel(dialog, text=prompt, anchor="w", justify="left").pack(
            fill="x", padx=20, pady=(18, 6)
        )
        
        entry = ctk.CTkEntry(dialog, width=380)
        entry.pack(fill="x", padx=20)
        
        if initial_value:
            entry.insert(0, initial_value)
            entry.select_range(0, "end")
        
        result = {"value": None}
        
        def on_ok():
            result["value"] = entry.get().strip()
            dialog.destroy()
        
        def on_cancel():
            result["value"] = None
            dialog.destroy()
        
        entry.bind("<Return>", lambda e: on_ok())
        entry.bind("<Escape>", lambda e: on_cancel())
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=14)
        ctk.CTkButton(buttons, text="ОК", width=100, command=on_ok).pack(side="right", padx=4)
        ctk.CTkButton(buttons, text="Отмена", width=100, command=on_cancel).pack(side="right", padx=4)
        
        # Вставка из буфера обмена работает и в диалоге
        self._register_paste(entry)
        
        # Центрируем окно диалога над основным
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 2
        dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        
        dialog.grab_set()
        entry.focus_set()
        
        self.wait_window(dialog)
        
        return result["value"]

    # ------------------------------------------------------------------
    # API-ключ подключения
    # ------------------------------------------------------------------

    def _generate_api_key(self):
        """Генерирует новый API-ключ для выбранного подключения."""
        import secrets
        
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        new_key = secrets.token_urlsafe(32)
        config.set_api_key(name, new_key)
        
        self._refresh_connections_table()
        self._update_selected_connection()
        self._save_and_apply()
        
        self.lbl_connection_status.configure(
            text=f"Новый ключ для подключения '{name}' создан", text_color="green")
        
        logger.info(f"New API key generated for connection '{name}'")
    
    def _copy_api_key(self):
        """Копирует ключ выбранного подключения в буфер обмена."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="Внимание: не выбрано подключение", text_color="orange")
            return
        
        connection = config.get_connection(name)
        api_keys = (connection or {}).get("api_keys") or []
        
        if not api_keys:
            self.lbl_connection_status.configure(text="Внимание: ключ подключения не задан", text_color="orange")
            return
        
        self._copy_to_clipboard(api_keys[0], self.btn_copy_key, "Копировать ключ")
    
    def _copy_connection_key(self, name: str):
        """Копирует ключ подключения (клик по иконке в таблице)."""
        connection = config.get_connection(name)
        api_keys = (connection or {}).get("api_keys") or []
        
        if not api_keys:
            self.lbl_connection_status.configure(
                text=f"Внимание: ключ подключения '{name}' не задан", text_color="orange")
            return
        
        self._copy_to_clipboard(api_keys[0], self.btn_copy_key, "Копировать ключ")
        
        self.lbl_connection_status.configure(
            text=f"Ключ подключения '{name}' скопирован", text_color="green")
    
    def _copy_to_clipboard(self, text: str, button, original_text: str):
        """Копирует текст в буфер обмена и показывает подтверждение."""
        if not pyperclip:
            return
        
        try:
            pyperclip.copy(text)
            button.configure(text="Готово", text_color="green")
            self.after(1500, lambda: button.configure(text=original_text, text_color="white"))
            logger.info("API key copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy API key: {e}")
    
    # ------------------------------------------------------------------
    # Вкладка API
    # ------------------------------------------------------------------

    def _create_api_tab(self):
        """Create API configuration tab."""
        api_config = config.api

        # Host
        ctk.CTkLabel(self.tab_api, text="Хост:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_api_host = ctk.CTkEntry(self.tab_api, width=300)
        self.entry_api_host.insert(0, api_config.get("host", "127.0.0.1"))
        self.entry_api_host.grid(row=0, column=1, padx=10, pady=10)

        # Port
        ctk.CTkLabel(self.tab_api, text="Порт:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_api_port = ctk.CTkEntry(self.tab_api, width=300)
        self.entry_api_port.insert(0, str(api_config.get("port", 5000)))
        self.entry_api_port.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(
            self.tab_api,
            text="API-ключи задаются для каждого подключения на вкладке «Подключения»",
            text_color="gray"
        ).grid(row=2, column=0, columnspan=2, padx=10, pady=6, sticky="w")

        # Требовать API-ключ для запросов
        self.switch_require_auth = ctk.CTkSwitch(
            self.tab_api,
            text="Требовать API-ключ для запросов",
            onvalue=True,
            offvalue=False
        )
        self.switch_require_auth.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        if api_config.get("require_auth", True):
            self.switch_require_auth.select()
        
        ctk.CTkLabel(
            self.tab_api,
            text="Если выключить — запросы выполняются без ключа (тестовый режим)",
            text_color="gray"
        ).grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="w")

        # Debug mode
        self.switch_debug = ctk.CTkSwitch(
            self.tab_api,
            text="Режим отладки",
            onvalue=True,
            offvalue=False
        )
        self.switch_debug.grid(row=5, column=0, columnspan=2, padx=10, pady=10)
        if api_config.get("debug", False):
            self.switch_debug.select()

        # Enable logging switch
        self.switch_logging = ctk.CTkSwitch(
            self.tab_api,
            text="Ведение логов в файл",
            onvalue=True,
            offvalue=False
        )
        self.switch_logging.grid(row=6, column=0, columnspan=2, padx=10, pady=10)
        app_config = config.app
        if app_config.get("enable_logging", True):
            self.switch_logging.select()

        # Bind right-click menu for API entry fields (Ctrl+V is native in CTkEntry)
        self.entry_api_host.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_api_host))
        self.entry_api_port.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_api_port))
        
        # Ctrl+V — привязка к внутреннему tk.Entry каждого поля
        self._register_paste(self.entry_api_host, self.entry_api_port)

    def _create_api_docs_tab(self):
        """Create API documentation tab."""
        # Переключатель подключений
        top_frame = ctk.CTkFrame(self.tab_api_docs, fg_color="transparent")
        top_frame.pack(fill="x", padx=12, pady=(12, 0))
        top_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(top_frame, text="Подключение:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        
        self.docs_connection_var = ctk.StringVar(value=config.default_connection)
        self.docs_connection_menu = ctk.CTkOptionMenu(
            top_frame,
            values=self._docs_connection_values(),
            variable=self.docs_connection_var,
            command=self._on_docs_connection_change,
            width=240
        )
        self.docs_connection_menu.grid(row=0, column=1, sticky="w")
        
        # Подсказка — отдельной строкой, чтобы переключатель её не перекрывал
        hint = ctk.CTkLabel(
            top_frame,
            text="Ссылки и curl-команды собираются для выбранного подключения",
            text_color="gray",
            anchor="w"
        )
        hint.grid(row=1, column=0, columnspan=2, pady=(4, 0), sticky="w")
        
        if not config.api.get("require_auth", True):
            ctk.CTkLabel(
                top_frame,
                text="Внимание: API-ключи не требуются — запросы выполняются без авторизации",
                text_color="orange",
                anchor="w"
            ).grid(row=2, column=0, columnspan=2, pady=(2, 0), sticky="w")
        
        self.docs_scroll_frame = ctk.CTkScrollableFrame(self.tab_api_docs, width=640, height=440)
        self.docs_scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        self._refresh_api_docs()
    
    def _docs_connection_values(self) -> List[str]:
        """Список подключений для переключателя в документации."""
        names = config.get_connection_names()
        return names if names else [config.default_connection]
    
    def _on_docs_connection_change(self, choice: str):
        """Переключение подключения в документации — обновляем ссылки."""
        self._refresh_api_docs()
    
    def _update_docs_connections(self):
        """Обновляет список подключений в переключателе документации."""
        if not hasattr(self, "docs_connection_menu"):
            return
        
        values = self._docs_connection_values()
        self.docs_connection_menu.configure(values=values)
        
        if self.docs_connection_var.get() not in values:
            self.docs_connection_var.set(config.default_connection)
    
    def _refresh_api_docs(self):
        """Перестраивает карточки эндпоинтов (актуальные хост, порт, ключ и подключение)."""
        if not hasattr(self, "docs_scroll_frame"):
            return
        
        self._update_docs_connections()
        
        self.docs_cards = []
        
        for child in self.docs_scroll_frame.winfo_children():
            child.destroy()
        
        # Function to copy text to clipboard
        def copy_to_clipboard(text, button, original_text):
            """Copy text to clipboard."""
            if not pyperclip:
                return
            
            try:
                pyperclip.copy(text)
                button.configure(text="Готово", text_color="green")
                self.after(2000, lambda: button.configure(text=original_text, text_color="white"))
            except Exception:
                button.configure(text="Ошибка", text_color="red")
        
        # Function to open URL in browser
        def open_in_browser(url, button):
            """Open URL in default browser."""
            try:
                webbrowser.open(url)
                button.configure(text="Готово", text_color="green")
                self.after(2000, lambda: button.configure(text="Открыть", text_color="white"))
            except Exception:
                button.configure(text="Ошибка", text_color="red")
        
        # Get base URL from config
        api_host = getattr(self, 'entry_api_host', None)
        api_port = getattr(self, 'entry_api_port', None)
        
        if api_host and api_port:
            base_url = f"http://{api_host.get()}:{api_port.get()}"
        else:
            base_url = "http://127.0.0.1:5000"
        
        # Выбранное подключение
        selected = self.docs_connection_var.get()
        selected_connection = config.get_connection(selected) or {}
        api_keys = selected_connection.get("api_keys", [])
        api_key = api_keys[0] if api_keys else "<API-KEY>"
        
        # Аутентификация может быть отключена — тогда ключ не нужен
        require_auth = bool(config.api.get("require_auth", True))
        
        # Для подключения по умолчанию работает короткая форма пути,
        # для остальных — именованная (/api/v1/c/<имя>/...)
        if selected == config.default_connection:
            connection_part = ""
        else:
            connection_part = f"/c/{selected}"
        
        # Endpoints list: (method, path, description, requires_auth)
        # path — часть после /api/v1
        endpoints = [
            ("GET", "/health", "Проверить здоровье сервиса", False),
            ("GET", "/info", "Получить информацию об API", False),
            ("GET", "/tables", "Получить список всех таблиц", True),
            ("GET", "/tables/{name}/columns", "Получить структуру таблицы (колонки)", True),
            ("GET", "/tables/{name}/select", "Выбрать данные из таблицы (SELECT с пагинацией)", True),
            ("POST", "/tables/{name}/insert", "Добавить одну запись в таблицу (INSERT)", True),
            ("POST", "/tables/{name}/batch-insert", "Массовая вставка записей (массив объектов)", True),
            ("POST", "/query", "Выполнить произвольный SQL запрос (SELECT)", True),
            ("GET", "/c/{connection}/tables", "То же, но для именованного подключения", True),
        ]
        
        # Method colors
        method_colors = {
            "GET": "#4CAF50",
            "POST": "#2196F3",
            "PUT": "#FF9800",
            "DELETE": "#F44336"
        }
        
        for method, path, desc, requires_auth in endpoints:
            endpoint_frame = ctk.CTkFrame(self.docs_scroll_frame)
            endpoint_frame.pack(fill="x", padx=5, pady=5)
            
            # Method and path
            method_color = method_colors.get(method, "#FFFFFF")
            ctk.CTkLabel(
                endpoint_frame,
                text=f"{method} {path}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=method_color
            ).pack(anchor="w", padx=10, pady=(10, 4))
            
            # Description
            ctk.CTkLabel(
                endpoint_frame,
                text=desc,
                text_color="gray",
                font=ctk.CTkFont(size=10)
            ).pack(anchor="w", padx=10)
            
            # Ссылка — отдельной строкой, чтобы длинный URL не выдавливал кнопки
            if path.startswith("/c/"):
                # Именованная форма — всегда с выбранным подключением
                url = f"{base_url}/api/v1{path.replace('{connection}', selected)}"
            else:
                url = f"{base_url}/api/v1{connection_part}{path.replace('{name}', 'users')}"
            
            ctk.CTkLabel(
                endpoint_frame,
                text=url,
                text_color="#64B5F6",
                font=ctk.CTkFont(size=10),
                anchor="w"
            ).pack(fill="x", padx=10, pady=(4, 0))
            
            # Кнопки — своей строкой, всегда видны
            buttons_frame = ctk.CTkFrame(endpoint_frame, fg_color="transparent")
            buttons_frame.pack(fill="x", padx=8, pady=(4, 8))
            
            # Копировать саму ссылку
            link_btn = ctk.CTkButton(buttons_frame, text="Скопировать ссылку", width=130)
            link_btn.pack(side="left", padx=2)
            link_btn.configure(
                command=lambda u=url, b=link_btn, t="Скопировать ссылку": copy_to_clipboard(u, b, t)
            )
            
            # Копировать готовую curl-команду
            if requires_auth and require_auth:
                curl = f'curl -H "X-API-Key: {api_key}" "{url}"'
            else:
                curl = f'curl "{url}"'
            
            curl_btn = ctk.CTkButton(buttons_frame, text="Команда curl", width=110)
            curl_btn.pack(side="left", padx=2)
            curl_btn.configure(
                command=lambda c=curl, b=curl_btn, t="Команда curl": copy_to_clipboard(c, b, t)
            )
            
            # Открыть в браузере: для защищённых — через страницу-«пробник»,
            # которая сама подставит заголовок X-API-Key
            if requires_auth and require_auth:
                browser_url = f"{base_url}/try?path={quote(url.replace(base_url, ''), safe='')}"
            else:
                browser_url = url
            
            open_btn = ctk.CTkButton(buttons_frame, text="Открыть", width=80)
            open_btn.pack(side="left", padx=2)
            open_btn.configure(command=lambda u=browser_url, b=open_btn: open_in_browser(u, b))
            
            # Структура карточки — используется в тестах и для отладки
            self.docs_cards.append({
                "method": method,
                "path": path,
                "description": desc,
                "url": url,
                "curl": curl,
                "requires_auth": requires_auth,
                "link_button": link_btn,
                "curl_button": curl_btn,
                "browser_button": open_btn,
            })

    # ------------------------------------------------------------------
    # Вспомогательное: Ctrl+V и контекстное меню
    # ------------------------------------------------------------------

    def _clipboard_text(self, entry=None) -> str:
        """Достаёт текст из буфера обмена.

        Args:
            entry: Виджет с фокусом (запасной источник — системный буфер Tk)

        Returns:
            Текст из буфера или пустая строка
        """
        if pyperclip:
            try:
                text = pyperclip.paste()
                if text:
                    return text
            except Exception as e:
                logger.debug(f"Failed to get clipboard: {e}")
        
        if entry is not None:
            try:
                return entry.clipboard_get()
            except tk.TclError:
                pass
        
        return ""
    
    def _insert_text(self, entry, text: str) -> bool:
        """Вставляет текст в позицию курсора (выделение заменяется).

        Args:
            entry: Внутренний виджет tk.Entry
            text: Текст для вставки

        Returns:
            bool: True если текст вставлен
        """
        if not entry or not text:
            return False
        
        try:
            try:
                entry.delete("sel.first", "sel.last")
            except tk.TclError:
                pass  # выделения нет
            
            try:
                cursor_pos = entry.index("insert")
            except tk.TclError:
                cursor_pos = 0
            
            entry.insert(cursor_pos, text)
            entry.icursor(cursor_pos + len(text))
            logger.debug(f"Pasted {len(text)} chars at position {cursor_pos}")
            return True
        except tk.TclError as e:
            logger.debug(f"Paste insert error: {e}")
            return False
    
    def _on_paste(self, event):
        """Обработчик Ctrl+V для текстовых полей.

        Привязывается к внутреннему виджету tk.Entry (widget-level binding):
        он срабатывает раньше class-привязки Tk, поэтому возврат "break"
        отменяет штатную вставку — текст вставляется ровно один раз.
        """
        entry = event.widget
        
        if not isinstance(entry, (tk.Entry, tk.Text)):
            inner = getattr(entry, "_entry", None)
            if inner is None:
                return None
            entry = inner
        
        text = self._clipboard_text(entry)
        
        if not text:
            return "break"
        
        self._insert_text(entry, text)
        return "break"
    
    def _register_paste(self, *entries):
        """Включает вставку из буфера обмена (Ctrl+V) для указанных полей.

        Args:
            *entries: Виджеты ввода (CTkEntry или tk.Entry)
        """
        for entry in entries:
            if entry is None:
                continue
            
            target = getattr(entry, "_entry", entry)
            
            try:
                target.bind("<Control-v>", self._on_paste, add="+")
                target.bind("<Control-V>", self._on_paste, add="+")
            except tk.TclError as e:
                logger.debug(f"Failed to bind paste for {entry}: {e}")
    
    def _show_paste_menu(self, event, widget):
        """Show context menu with paste option."""
        menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white")
        
        def paste_action():
            target = getattr(widget, "_entry", widget)
            text = self._clipboard_text(target)
            if text:
                self._insert_text(target, text)
        
        menu.add_command(label="Вставить", command=paste_action)
        menu.tk_popup(event.x_root, event.y_root)
    
    def _setup_paste_functionality(self):
        """Setup paste functionality for entry fields (right-click menu only)."""
        # Bind right-click menu for all entry fields
        db_entries = [
            self.entry_dsn, self.entry_host, self.entry_port, self.entry_dbname,
            self.entry_user, self.entry_password
        ]
        for entry in db_entries:
            # CTkEntry has native Ctrl+V support, just bind right-click menu
            entry.bind("<Button-3>", lambda e, w=entry: self._show_paste_menu(e, w))
        
        # Ctrl+V — привязка к внутреннему tk.Entry каждого поля
        self._register_paste(*db_entries)

    def _parse_dsn(self):
        """Parse DSN string and fill connection fields."""
        from ..api.database import parse_dsn

        dsn_string = self.entry_dsn.get().strip()
        if not dsn_string:
            self.lbl_connection_status.configure(
                text="Внимание: введите DSN строку!",
                text_color="orange"
            )
            return

        try:
            parsed = parse_dsn(dsn_string)

            # Fill fields with parsed values
            self.entry_host.delete(0, "end")
            self.entry_host.insert(0, parsed.get("host", ""))

            self.entry_port.delete(0, "end")
            self.entry_port.insert(0, str(parsed.get("port", 5432)))

            self.entry_dbname.delete(0, "end")
            self.entry_dbname.insert(0, parsed.get("database", ""))

            self.entry_user.delete(0, "end")
            self.entry_user.insert(0, parsed.get("user", ""))

            self.entry_password.delete(0, "end")
            self.entry_password.insert(0, parsed.get("password", ""))

            self.lbl_connection_status.configure(
                text="DSN успешно разобран!",
                text_color="green"
            )
        except ValueError as e:
            self.lbl_connection_status.configure(
                text=f"Внимание:  Ошибка разбора DSN: {str(e)}",
                text_color="orange"
            )
        except Exception as e:
            self.lbl_connection_status.configure(
                text=f"Ошибка: {str(e)}",
                text_color="red"
            )

    # ------------------------------------------------------------------
    # Footer: сохранение и управление API
    # ------------------------------------------------------------------

    def _create_footer(self):
        """Create footer section with action buttons."""
        self.footer_frame = ctk.CTkFrame(self, height=60)
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.footer_frame.grid_columnconfigure(0, weight=1)
        self.footer_frame.grid_columnconfigure(1, weight=1)

        # Save button
        self.btn_save = ctk.CTkButton(
            self.footer_frame,
            text="Сохранить настройки",
            command=self._save_settings
        )
        self.btn_save.grid(row=0, column=0, padx=10, pady=10)

        # Start/Stop API button
        self.btn_toggle_api = ctk.CTkButton(
            self.footer_frame,
            text="Запустить API",
            command=self._toggle_api
        )
        self.btn_toggle_api.grid(row=0, column=1, padx=10, pady=10)

    def _save_settings(self):
        """Save current settings to config file."""
        # Валидация порта API
        api_port_text = self.entry_api_port.get().strip()
        if not api_port_text.isdigit():
            self.lbl_connection_status.configure(
                text=f"Внимание:  Порт API должен быть числом (получено: '{api_port_text}')",
                text_color="orange"
            )
            return
        
        # Применяем правки редактора к выбранному подключению
        if not self._apply_editor_to_connection():
            return
        
        # Update API config (глобальные настройки сервера)
        config.update_api(
            host=self.entry_api_host.get().strip(),
            port=int(api_port_text),
            debug=self.switch_debug.get(),
            require_auth=self.switch_require_auth.get()
        )
        
        # Update app config
        config.update_app(
            enable_logging=self.switch_logging.get()
        )
        
        try:
            config.save()
        except OSError as e:
            self.lbl_connection_status.configure(
                text=f"Ошибка:  Не удалось сохранить настройки: {e}",
                text_color="red"
            )
            return
        
        # Применяем изменения к работающему API (ключи и параметры БД — без перезапуска)
        self._reload_runtime_config()
        
        logger.info("Settings saved")
        self.lbl_connection_status.configure(text="Настройки сохранены", text_color="green")
    
    def _save_and_apply(self):
        """Сохраняет конфиг и применяет его к работающему API."""
        try:
            config.save()
        except OSError as e:
            logger.error(f"Failed to save configuration: {e}")
            self.lbl_connection_status.configure(
                text=f"Ошибка:  Не удалось сохранить настройки: {e}",
                text_color="red"
            )
            return
        
        self._reload_runtime_config()
    
    def _reload_runtime_config(self):
        """Применяет текущий конфиг к работающему серверу (hot-reload)."""
        registry = get_registry()
        
        if registry:
            registry.reload(config)
            registry.start_background_connect()
            logger.info("Runtime configuration reloaded")
        
        self._refresh_connections_table()
        self._update_selected_connection()
        self._refresh_api_docs()
    
    def _test_connection(self):
        """Test database connection for the selected connection."""
        from ..api.database import Database

        # Значения из полей редактора
        host = self.entry_host.get().strip()
        port_text = self.entry_port.get().strip()
        dbname = self.entry_dbname.get().strip()
        user = self.entry_user.get()
        password = self.entry_password.get()
        
        # Validation
        if not all([host, port_text, dbname, user]):
            self.lbl_connection_status.configure(
                text="Внимание: заполните все обязательные поля!",
                text_color="orange"
            )
            return
        
        if not port_text.isdigit():
            self.lbl_connection_status.configure(
                text=f"Внимание:  Порт должен быть числом (получено: '{port_text}')",
                text_color="orange"
            )
            return
        
        # Show loading state
        original_text = self.btn_test.cget("text")
        self.btn_test.configure(text="Проверка...", state="disabled")
        self.lbl_connection_status.configure(text="⏳ Подключение...", text_color="gray")
        self.update()
        
        try:
            db = Database({
                "host": host,
                "port": int(port_text),
                "database": dbname,
                "user": user,
                "password": password
            })
            
            is_connected = db.is_connected()
            db.close(reason="connection test")
            
            if is_connected:
                self.lbl_connection_status.configure(
                    text="Подключено",
                    text_color="green"
                )
            else:
                # Показываем причину: неверный пароль / порт закрыт / DNS и т.д.
                reason = db.last_error_message or "причина неизвестна, подробности в app.log"
                self.lbl_connection_status.configure(
                    text=f"Не удалось подключиться: {reason}",
                    text_color="red"
                )
        except ValueError:
            self.lbl_connection_status.configure(
                text="Внимание: порт должен быть числом!",
                text_color="orange"
            )
        except Exception as e:
            self.lbl_connection_status.configure(
                text=f"Ошибка: {str(e)}",
                text_color="red"
            )
        finally:
            self.btn_test.configure(text=original_text, state="normal")

    def _toggle_api(self):
        """Toggle API server start/stop."""
        if self.api_server and self.api_server.is_running():
            self.api_server.stop()
            self.btn_toggle_api.configure(text="Запустить API")
            self.status_label.configure(text="API: Остановлен")
        else:
            api_port_text = self.entry_api_port.get().strip()
            
            if not api_port_text.isdigit():
                self.lbl_connection_status.configure(
                    text=f"Внимание:  Порт API должен быть числом (получено: '{api_port_text}')",
                    text_color="orange"
                )
                return
            
            self._save_settings()
            
            if self.api_server:
                started = self.api_server.start(
                    host=self.entry_api_host.get().strip(),
                    port=int(api_port_text)
                )
                
                if started:
                    self.btn_toggle_api.configure(text="Остановить API")
                    self.status_label.configure(
                        text=f"API: Работает на {self.entry_api_host.get()}:{self.entry_api_port.get()}")
                else:
                    self.btn_toggle_api.configure(text="Запустить API")
                    self.status_label.configure(text="API: Ошибка запуска")
                    self.lbl_connection_status.configure(
                        text="Не удалось запустить API — порт уже занят другим процессом",
                        text_color="red"
                    )

    def _update_api_status(self):
        """Periodically update API status."""
        if self.api_server:
            if self.api_server.is_running():
                connections_count = len(config.connections)
                self.status_label.configure(text=f"API: Работает ({connections_count} подкл.)")
                self.btn_toggle_api.configure(text="Остановить API")
            else:
                self.status_label.configure(text="API: Не запущен")
                self.btn_toggle_api.configure(text="Запустить API")
        
        # Показываем последнюю ошибку БД, если подключение было недоступно
        self._update_last_db_error()
        
        # Обновляем статус подключений (цветная точка в таблице)
        self._update_connection_status()
        
        # Schedule next update
        self.after(2000, self._update_api_status)

    def _update_last_db_error(self):
        """Показывает в статусе состояние подключения к БД и причину ошибки."""
        registry = get_registry()
        if not registry:
            return
        
        profile = registry.get(self._current_connection) if self._current_connection else registry.get_default()
        if not profile:
            return
        
        if not profile.is_db_created:
            self.lbl_db_state.configure(
                text="БД: соединение создаётся при первом запросе к API",
                text_color="gray")
            return
        
        error = profile.last_error
        
        if profile.db.is_connected():
            self.lbl_db_state.configure(text="БД: подключено", text_color="green")
            return
        
        message = (error or {}).get("message") or "нет соединения"
        hint = (error or {}).get("user_hint") or ""
        text = f"Ошибка:  БД недоступна: {message}" + (f" — {hint}" if hint else "")
        
        current = self.lbl_db_state.cget("text")
        if not current.startswith("Ошибка:  БД недоступна"):
            self.lbl_db_state.configure(text=text, text_color="red")

    def run(self):
        """Start the GUI main loop."""
        self.mainloop()

    # ------------------------------------------------------------------
    # Системный трей
    # ------------------------------------------------------------------

    def _create_tray_icon(self):
        """Create system tray icon with menu."""
        global _tray_icon
        if not PYTRAY_AVAILABLE:
            logger.warning("pystray not available, tray icon disabled")
            return
        
        # Create a simple icon programmatically
        def create_icon_image():
            """Create icon image."""
            img = Image.new('RGB', (64, 64), color='#2d2d2d')
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], outline='#4a9eff', width=3)
            draw.line([32, 20, 32, 44], fill='#4a9eff', width=2)
            draw.ellipse([22, 28, 42, 40], outline='#4a9eff', width=2)
            return img
        
        # Tooltip text
        def get_tooltip_text() -> str:
            """Get tooltip text."""
            global _last_activity_time
            status = "Работает" if (self.api_server and self.api_server.is_running()) else "Не запущен"
            time_str = _last_activity_time.strftime("%Y-%m-%d %H:%M:%S") if _last_activity_time else "N/A"
            lines = [
                "ApiPostgresConnector",
                f"Статус: {status}",
                f"Подключение по умолчанию: {config.default_connection}",
                f"Последняя активность: {time_str}"
            ]
            
            registry = get_registry()
            if registry:
                profile = registry.get_default()
                if profile and profile.is_db_created and not profile.db.is_connected():
                    error = profile.last_error
                    if error:
                        lines.append(f"Ошибка БД: {error.get('message')}")
            
            return "\n".join(lines)
        
        # Menu actions
        def on_quit(icon, item):
            """Quit application."""
            global _tray_icon
            if _tray_icon:
                _tray_icon.stop()
            self.quit()
        
        def on_show(icon, item):
            """Show window on left click."""
            self.after(0, self._restore_window)
        
        def on_toggle_api(icon, item):
            """Toggle API server on/off."""
            self.after(0, self._toggle_api)
        
        def on_hover(icon, item):
            """Update tooltip on hover."""
            if _tray_icon:
                _tray_icon.title = get_tooltip_text()
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Показать", on_show, default=True),
            pystray.MenuItem("Запустить/Остановить API", on_toggle_api),
            pystray.MenuItem("Выход", on_quit)
        )
        
        try:
            _tray_icon = pystray.Icon(
                "ApiPostgresConnector",
                create_icon_image(),
                title=get_tooltip_text(),
                menu=menu
            )
            
            # Run tray icon in a separate thread
            tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
            tray_thread.start()
            
            logger.info("System tray icon created")
        except Exception as e:
            logger.error(f"Failed to create tray icon: {e}")

    def _restore_window(self):
        """Restore window from tray."""
        self.deiconify()
        self.state('normal')
        self.lift()
        self.focus_force()

    def _minimize_to_tray(self):
        """Minimize window to tray."""
        # Проверяем, что окно минимизировано (iconic)
        if self.state() == 'iconic':
            if config.app.get("minimize_to_tray", False):
                # Используем after для отложенного выполнения, чтобы избежать конфликтов
                self.after(100, self._do_minimize_to_tray)

    def _on_close_window(self):
        """Handle window close event (X button)."""
        if config.app.get("minimize_to_tray", True):
            # Сворачиваем в трей вместо закрытия
            self.withdraw()
            # Try to create tray icon if available and not already created
            if PYTRAY_AVAILABLE:
                try:
                    if _tray_icon is None:
                        self._create_tray_icon()
                except Exception as e:
                    logger.warning(f"Failed to create tray icon: {e}")
                    # Fallback: just keep window hidden, tray not critical
        else:
            # Полностью закрываем приложение
            self.quit()

    def _do_minimize_to_tray(self):
        """Actually minimize to tray."""
        self.withdraw()
        if PYTRAY_AVAILABLE:
            try:
                if _tray_icon is None:
                    self._create_tray_icon()
            except Exception as e:
                logger.warning(f"Failed to create tray icon: {e}")

    def update_tray_status(self):
        """Update tray icon status after API request."""
        global _last_activity_time
        _last_activity_time = datetime.now()
        
        if _tray_icon:
            status = "Работает" if (self.api_server and self.api_server.is_running()) else "Не запущен"
            time_str = _last_activity_time.strftime("%Y-%m-%d %H:%M:%S")
            _tray_icon.title = f"ApiPostgresConnector\nСтатус: {status}\nПоследняя активность: {time_str}"

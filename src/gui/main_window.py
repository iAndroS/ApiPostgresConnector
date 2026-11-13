"""Main GUI window for ApiPostgresConnector."""
import logging
import threading
import webbrowser
from datetime import datetime
from typing import Optional, Any

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
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
        
        # NOTE: CTkEntry 5.2.x supports Ctrl+V natively
        # We add explicit key binding to ensure it works properly
        self._setup_ctrlv_binding()
        
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
        """Create connections tab: список подключений, редактор и API-ключи."""
        container = ctk.CTkScrollableFrame(self.tab_connections)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Таблица подключений ---
        columns = ("name", "host", "port", "db", "user", "keys")
        self.tree_connections = ttk.Treeview(
            container, columns=columns, show="headings", height=6, selectmode="browse"
        )
        
        headings = {
            "name": "Имя",
            "host": "Хост",
            "port": "Порт",
            "db": "База",
            "user": "Пользователь",
            "keys": "Ключей"
        }
        widths = {"name": 130, "host": 120, "port": 55, "db": 100, "user": 100, "keys": 55}
        
        for column in columns:
            self.tree_connections.heading(column, text=headings[column])
            self.tree_connections.column(column, width=widths[column], anchor="w")
        
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                        background="#2b2b2b",
                        fieldbackground="#2b2b2b",
                        foreground="#ffffff",
                        rowheight=22,
                        borderwidth=0)
        style.configure("Dark.Treeview.Heading",
                        background="#3a3a3a",
                        foreground="#ffffff",
                        relief="flat")
        style.map("Dark.Treeview",
                  background=[("selected", "#4a9eff")],
                  foreground=[("selected", "#ffffff")])
        self.tree_connections.configure(style="Dark.Treeview")
        
        self.tree_connections.pack(fill="x", padx=4, pady=(4, 0))
        self.tree_connections.bind("<<TreeviewSelect>>", self._on_connection_select)
        
        # --- Кнопки управления подключениями ---
        buttons_frame = ctk.CTkFrame(container, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=4, pady=6)
        
        ctk.CTkButton(buttons_frame, text="Добавить", width=85,
                      command=self._add_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Переименовать", width=105,
                      command=self._rename_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Дублировать", width=100,
                      command=self._duplicate_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="Удалить", width=75,
                      command=self._remove_connection).pack(side="left", padx=2)
        ctk.CTkButton(buttons_frame, text="По умолчанию", width=110,
                      command=self._set_default_connection).pack(side="left", padx=2)
        
        ctk.CTkLabel(container, text="Параметры подключения", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=4, pady=(6, 2))
        
        editor = ctk.CTkFrame(container, fg_color="transparent")
        editor.pack(fill="x", padx=4)
        editor.grid_columnconfigure(1, weight=1)
        
        # DSN
        ctk.CTkLabel(editor, text="DSN:").grid(row=0, column=0, padx=4, pady=3, sticky="w")
        self.entry_dsn = ctk.CTkEntry(editor, width=240)
        self.entry_dsn.grid(row=0, column=1, padx=4, pady=3, sticky="ew")
        ctk.CTkButton(editor, text="Из DSN", width=70,
                      command=self._parse_dsn).grid(row=0, column=2, padx=4, pady=3)
        
        # Host
        ctk.CTkLabel(editor, text="Хост:").grid(row=1, column=0, padx=4, pady=3, sticky="w")
        self.entry_host = ctk.CTkEntry(editor, width=240)
        self.entry_host.grid(row=1, column=1, padx=4, pady=3, sticky="ew")
        
        # Port
        ctk.CTkLabel(editor, text="Порт:").grid(row=2, column=0, padx=4, pady=3, sticky="w")
        self.entry_port = ctk.CTkEntry(editor, width=240)
        self.entry_port.grid(row=2, column=1, padx=4, pady=3, sticky="ew")
        
        # Database name
        ctk.CTkLabel(editor, text="База данных:").grid(row=3, column=0, padx=4, pady=3, sticky="w")
        self.entry_dbname = ctk.CTkEntry(editor, width=240)
        self.entry_dbname.grid(row=3, column=1, padx=4, pady=3, sticky="ew")
        
        # User
        ctk.CTkLabel(editor, text="Пользователь:").grid(row=4, column=0, padx=4, pady=3, sticky="w")
        self.entry_user = ctk.CTkEntry(editor, width=240)
        self.entry_user.grid(row=4, column=1, padx=4, pady=3, sticky="ew")
        
        # Password
        ctk.CTkLabel(editor, text="Пароль:").grid(row=5, column=0, padx=4, pady=3, sticky="w")
        self.entry_password = ctk.CTkEntry(editor, width=240, show="*")
        self.entry_password.grid(row=5, column=1, padx=4, pady=3, sticky="ew")
        
        self.btn_test = ctk.CTkButton(
            editor, text="Проверить подключение", width=160, command=self._test_connection
        )
        self.btn_test.grid(row=5, column=2, padx=4, pady=3)
        
        # Connection status
        self.lbl_connection_status = ctk.CTkLabel(editor, text="", anchor="w")
        self.lbl_connection_status.grid(row=6, column=0, columnspan=3, padx=4, pady=4, sticky="w")
        
        # --- API-ключи выбранного подключения ---
        ctk.CTkLabel(container, text="API-ключи подключения", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=4, pady=(6, 2))
        
        self.keys_listbox = tk.Listbox(container, height=4, bg="#2b2b2b", fg="#ffffff",
                                       selectbackground="#4a9eff", highlightthickness=0,
                                       relief="flat", activestyle="none")
        self.keys_listbox.pack(fill="x", padx=4)
        
        keys_buttons = ctk.CTkFrame(container, fg_color="transparent")
        keys_buttons.pack(fill="x", padx=4, pady=6)
        
        ctk.CTkButton(keys_buttons, text="Сгенерировать", width=110,
                      command=self._generate_api_key).pack(side="left", padx=2)
        ctk.CTkButton(keys_buttons, text="Добавить", width=85,
                      command=self._add_api_key).pack(side="left", padx=2)
        ctk.CTkButton(keys_buttons, text="Удалить", width=75,
                      command=self._remove_api_key).pack(side="left", padx=2)
        
        self.btn_copy_key = ctk.CTkButton(keys_buttons, text="📋", width=40,
                                          command=self._copy_api_key)
        self.btn_copy_key.pack(side="left", padx=2)
        
        # Right-click paste menu for all entry fields
        self._setup_paste_functionality()
        
        # Заполняем таблицу и редактор после создания всех виджетов
        self._refresh_connections_tree()

    def _refresh_connections_tree(self):
        """Перерисовывает таблицу подключений."""
        if not hasattr(self, "tree_connections"):
            return
        
        for item in self.tree_connections.get_children():
            self.tree_connections.delete(item)
        
        for connection in config.connections:
            db = connection.get("database", {})
            self.tree_connections.insert(
                "", "end", iid=connection.get("name"),
                values=(
                    connection.get("name", ""),
                    db.get("host", ""),
                    db.get("port", ""),
                    db.get("database", ""),
                    db.get("user", ""),
                    len(connection.get("api_keys", []))
                )
            )
        
        default_name = config.default_connection
        if default_name and self.tree_connections.exists(default_name):
            self.tree_connections.item(default_name, tags=("default",))
            self.tree_connections.tag_configure("default", foreground="#7ddf7d")
        
        if self._current_connection and self.tree_connections.exists(self._current_connection):
            self.tree_connections.selection_set(self._current_connection)
        elif self.tree_connections.get_children():
            first = self.tree_connections.get_children()[0]
            self.tree_connections.selection_set(first)
            self._load_connection_into_editor(first)
    
    def _on_connection_select(self, event=None):
        """Загружает выбранное подключение в редактор."""
        selection = self.tree_connections.selection()
        if not selection:
            return
        
        name = selection[0]
        if name == self._current_connection:
            return
        
        # Перед переключением сохраняем правки предыдущего подключения
        self._apply_editor_to_connection()
        self._load_connection_into_editor(name)
    
    def _load_connection_into_editor(self, name: str):
        """Заполняет поля редактора данными подключения."""
        connection = config.get_connection(name)
        if not connection:
            return
        
        db = connection.get("database", {})
        self._current_connection = name
        
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
        
        self.keys_listbox.delete(0, "end")
        for key in connection.get("api_keys", []):
            self.keys_listbox.insert("end", key)
        
        self.lbl_connection_status.configure(text=f"Подключение: {name}", text_color="gray")
    
    def _apply_editor_to_connection(self) -> bool:
        """Переносит значения из полей редактора в конфиг выбранного подключения.

        Returns:
            bool: True если значения применены, False при ошибке валидации
        """
        name = self._current_connection
        if not name:
            return True
        
        connection = config.get_connection(name)
        if not connection:
            return True
        
        port_text = self.entry_port.get().strip()
        if not port_text.isdigit():
            self.lbl_connection_status.configure(
                text=f"⚠️ Порт подключения должен быть числом (получено: '{port_text}')",
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
        
        connection["api_keys"] = list(self.keys_listbox.get(0, "end"))
        
        return True
    
    # ------------------------------------------------------------------
    # Управление подключениями
    # ------------------------------------------------------------------

    def _add_connection(self):
        """Создаёт новое подключение."""
        name = simpledialog.askstring(
            "Новое подключение",
            "Название подключения:",
            parent=self
        )
        
        if not name or not name.strip():
            return
        
        name = name.strip()
        
        try:
            config.add_connection(name)
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"⚠️ {e}", text_color="orange")
            return
        
        # Новому подключению сразу генерируем API-ключ
        try:
            config.ensure_api_key(name)
        except Exception as e:
            logger.warning(f"Failed to generate API key for '{name}': {e}")
        
        config.save()
        self._refresh_connections_tree()
        self._load_connection_into_editor(name)
        self._reload_runtime_config()
        self.lbl_connection_status.configure(text=f"✅ Создано подключение '{name}'", text_color="green")
    
    def _rename_connection(self):
        """Переименовывает выбранное подключение."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        new_name = simpledialog.askstring(
            "Переименование",
            "Новое название:",
            initialvalue=name,
            parent=self
        )
        
        if not new_name or not new_name.strip() or new_name.strip() == name:
            return
        
        try:
            config.rename_connection(name, new_name.strip())
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"⚠️ {e}", text_color="orange")
            return
        
        self._current_connection = new_name.strip()
        config.save()
        self._refresh_connections_tree()
        self._load_connection_into_editor(new_name.strip())
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"✅ Подключение переименовано в '{new_name.strip()}'", text_color="green")
    
    def _duplicate_connection(self):
        """Создаёт копию выбранного подключения."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        new_name = simpledialog.askstring(
            "Дублирование",
            "Название копии:",
            initialvalue=f"{name}-copy",
            parent=self
        )
        
        if not new_name or not new_name.strip():
            return
        
        new_name = new_name.strip()
        source = config.get_connection(name)
        
        try:
            config.add_connection(
                new_name,
                database=dict(source.get("database", {})),
                api_keys=list(source.get("api_keys", []))
            )
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"⚠️ {e}", text_color="orange")
            return
        
        config.save()
        self._refresh_connections_tree()
        self._load_connection_into_editor(new_name)
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"✅ Создана копия '{new_name}'", text_color="green")
    
    def _remove_connection(self):
        """Удаляет выбранное подключение."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        if not self._ask_confirmation(f"Удалить подключение '{name}'?"):
            return
        
        if not config.remove_connection(name):
            self.lbl_connection_status.configure(
                text="⚠️ Нельзя удалить последнее подключение", text_color="orange")
            return
        
        self._current_connection = None
        config.save()
        self._refresh_connections_tree()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(text=f"✅ Подключение '{name}' удалено", text_color="green")
    
    def _set_default_connection(self):
        """Назначает выбранное подключение подключением по умолчанию."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        try:
            config.set_default_connection(name)
        except ValueError as e:
            self.lbl_connection_status.configure(text=f"⚠️ {e}", text_color="orange")
            return
        
        config.save()
        self._refresh_connections_tree()
        self._reload_runtime_config()
        self.lbl_connection_status.configure(
            text=f"✅ Подключением по умолчанию назначено '{name}'", text_color="green")
    
    def _ask_confirmation(self, message: str) -> bool:
        """Показывает диалог подтверждения."""
        from tkinter import messagebox
        return messagebox.askyesno("Подтверждение", message, parent=self)

    # ------------------------------------------------------------------
    # API-ключи
    # ------------------------------------------------------------------

    def _generate_api_key(self):
        """Generate new API key for the selected connection."""
        import secrets
        
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        new_key = secrets.token_urlsafe(32)
        self.keys_listbox.insert("end", new_key)
        self._apply_editor_to_connection()
        self._save_and_apply()
        logger.info(f"New API key generated for connection '{name}'")
    
    def _add_api_key(self):
        """Adds a manually entered API key to the selected connection."""
        name = self._current_connection
        if not name:
            self.lbl_connection_status.configure(text="⚠️ Не выбрано подключение", text_color="orange")
            return
        
        new_key = simpledialog.askstring(
            "Новый API-ключ",
            "Введите ключ:",
            parent=self
        )
        
        if not new_key or not new_key.strip():
            return
        
        self.keys_listbox.insert("end", new_key.strip())
        self._apply_editor_to_connection()
        self._save_and_apply()
    
    def _remove_api_key(self):
        """Removes the selected API key from the list."""
        selection = self.keys_listbox.curselection()
        if not selection:
            return
        
        self.keys_listbox.delete(selection[0])
        self._apply_editor_to_connection()
        self._save_and_apply()
    
    def _copy_api_key(self):
        """Copy API key to clipboard."""
        if not pyperclip:
            return
        
        selection = self.keys_listbox.curselection()
        
        if selection:
            api_key = self.keys_listbox.get(selection[0])
        else:
            api_key = self.keys_listbox.get(0, "end").split("\n")[0]
        
        if not api_key:
            return
        
        try:
            pyperclip.copy(api_key)
            original_text = self.btn_copy_key.cget("text")
            self.btn_copy_key.configure(text="✅", text_color="green")
            self.after(1500, lambda: self.btn_copy_key.configure(text="📋", text_color="white"))
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

        # Debug mode
        self.switch_debug = ctk.CTkSwitch(
            self.tab_api,
            text="Режим отладки",
            onvalue=True,
            offvalue=False
        )
        self.switch_debug.grid(row=4, column=0, columnspan=2, padx=10, pady=10)
        if api_config.get("debug", False):
            self.switch_debug.select()

        # Enable logging switch
        self.switch_logging = ctk.CTkSwitch(
            self.tab_api,
            text="Ведение логов в файл",
            onvalue=True,
            offvalue=False
        )
        self.switch_logging.grid(row=5, column=0, columnspan=2, padx=10, pady=10)
        app_config = config.app
        if app_config.get("enable_logging", True):
            self.switch_logging.select()

        # Bind right-click menu for API entry fields (Ctrl+V is native in CTkEntry)
        self.entry_api_host.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_api_host))
        self.entry_api_port.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_api_port))

    def _create_api_docs_tab(self):
        """Create API documentation tab."""
        scroll_frame = ctk.CTkScrollableFrame(self.tab_api_docs, width=640, height=480)
        scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Function to copy URL to clipboard
        def copy_to_clipboard(text, button):
            """Copy text to clipboard."""
            if pyperclip:
                try:
                    pyperclip.copy(text)
                    button.configure(text="✅ Скопировано!", text_color="green")
                    self.after(2000, lambda: button.configure(text="📋", text_color="white"))
                except Exception:
                    button.configure(text="❌ Ошибка", text_color="red")

        # Function to open URL in browser
        def open_in_browser(url, button):
            """Open URL in default browser."""
            try:
                webbrowser.open(url)
                button.configure(text="✅ Открыто!", text_color="green")
                self.after(2000, lambda: button.configure(text="🌐", text_color="white"))
            except Exception:
                button.configure(text="❌ Ошибка", text_color="red")

        # Get base URL from config
        api_host = getattr(self, 'entry_api_host', None)
        api_port = getattr(self, 'entry_api_port', None)
        if api_host and api_port:
            base_url = f"http://{api_host.get()}:{api_port.get()}"
        else:
            base_url = "http://127.0.0.1:5000"
        
        # Ключ подключения по умолчанию — для готовых curl-команд
        default_connection = config.get_connection(config.default_connection) or {}
        api_keys = default_connection.get("api_keys", [])
        api_key = api_keys[0] if api_keys else "<API-KEY>"
        connection_name = config.default_connection
        
        # Endpoints list: (method, path, description, requires_auth)
        endpoints = [
            ("GET", "/api/v1/health", "Проверить здоровье сервиса", False),
            ("GET", "/api/v1/info", "Получить информацию об API", False),
            ("GET", "/api/v1/tables", "Получить список всех таблиц", True),
            ("GET", "/api/v1/tables/{name}/columns", "Получить структуру таблицы (колонки)", True),
            ("GET", "/api/v1/tables/{name}/select", "Выбрать данные из таблицы (SELECT с пагинацией)", True),
            ("POST", "/api/v1/tables/{name}/insert", "Добавить одну запись в таблицу (INSERT)", True),
            ("POST", "/api/v1/tables/{name}/batch-insert", "Массовая вставка записей (массив объектов)", True),
            ("POST", "/api/v1/query", "Выполнить произвольный SQL запрос (SELECT)", True),
            ("GET", "/api/v1/c/{connection}/tables", "То же, но для именованного подключения", True),
        ]

        # Method colors
        method_colors = {
            "GET": "#4CAF50",
            "POST": "#2196F3",
            "PUT": "#FF9800",
            "DELETE": "#F44336"
        }

        for method, path, desc, requires_auth in endpoints:
            # Endpoint frame
            endpoint_frame = ctk.CTkFrame(scroll_frame)
            endpoint_frame.pack(fill="x", padx=5, pady=5)

            # Method and path
            method_color = method_colors.get(method, "#FFFFFF")
            ctk.CTkLabel(
                endpoint_frame,
                text=f"{method} {path}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=method_color
            ).pack(anchor="w", padx=10, pady=(10, 5))

            # Description
            ctk.CTkLabel(
                endpoint_frame,
                text=desc,
                text_color="gray",
                font=ctk.CTkFont(size=10)
            ).pack(anchor="w", padx=10)

            # URL and buttons frame - horizontal layout
            url_buttons_frame = ctk.CTkFrame(endpoint_frame, fg_color="transparent")
            url_buttons_frame.pack(fill="x", padx=5, pady=5)

            # URL label
            url = f"{base_url}{path.replace('{name}', 'users').replace('{connection}', connection_name)}"
            ctk.CTkLabel(
                url_buttons_frame,
                text=url,
                text_color="#64B5F6",
                font=ctk.CTkFont(size=10)
            ).pack(side="left", padx=5)

            # Buttons frame
            buttons_frame = ctk.CTkFrame(url_buttons_frame, fg_color="transparent")
            buttons_frame.pack(side="right", padx=5)

            # Copy button — для защищённых эндпоинтов копируем готовую curl-команду
            copy_btn = ctk.CTkButton(
                buttons_frame,
                text="📋",
                width=30
            )
            copy_btn.pack(side="left", padx=2)
            
            if requires_auth:
                curl = f'curl -H "X-API-Key: {api_key}" "{url}"'
            else:
                curl = f'curl "{url}"'
            
            # Fix closure with proper lambda
            copy_btn.configure(command=lambda u=curl, b=copy_btn: copy_to_clipboard(u, b))

            # Open in browser — только для эндпоинтов без авторизации
            if not requires_auth:
                open_btn = ctk.CTkButton(
                    buttons_frame,
                    text="🌐",
                    width=30
                )
                open_btn.pack(side="left", padx=2)
                open_btn.configure(command=lambda u=url, b=open_btn: open_in_browser(u, b))

    # ------------------------------------------------------------------
    # Вспомогательное: Ctrl+V и контекстное меню
    # ------------------------------------------------------------------

    def _bind_ctrlv_to_entry(self, ctk_entry):
        """Bind Ctrl+V to internal _entry of CTkEntry widget.
        
        CTkEntry wraps tk.Entry in _entry attribute.
        We bind directly to _entry to handle paste properly.
        """
        if hasattr(ctk_entry, '_entry') and ctk_entry._entry:
            ctk_entry._entry.bind("<Control-v>", self._on_ctrl_v)
            ctk_entry._entry.bind("<Control-V>", self._on_ctrl_v)
            logger.debug(f"Bound Ctrl+V to _entry of {ctk_entry}")

    def _setup_ctrlv_binding(self):
        """Setup Ctrl+V binding for all Entry widgets.
        
        Uses bind_all to catch Ctrl+V events globally and redirect them
        to the focused widget with proper clipboard handling.
        """
        # Bind Ctrl+V globally to catch it for all Entry widgets
        # Using focus_get() to get the focused widget
        self.bind_all("<Control-v>", self._on_ctrl_v)
        self.bind_all("<Control-V>", self._on_ctrl_v)
        logger.debug("Ctrl+V global binding set up")

    def _on_ctrl_v(self, event):
        """Handle Ctrl+V paste event.
        
        Gets clipboard content and inserts into focused widget.
        Works with both tk.Entry and CTkEntry widgets.
        """
        # Check if event widget is a CTkEntry or tk.Entry
        widget = event.widget
        
        if not pyperclip:
            return None
        
        # Get clipboard text
        try:
            text = pyperclip.paste()
            if not text:
                return "break"
        except Exception as e:
            logger.debug(f"Failed to get clipboard: {e}")
            return None
        
        # Find the entry widget to insert into
        entry = None
        
        # Check if it's CTkEntry (has _entry attribute)
        if hasattr(widget, '_entry') and widget._entry:
            entry = widget._entry
        # Check if it's a regular tk.Entry
        elif hasattr(widget, 'insert') and hasattr(widget, 'delete'):
            entry = widget
        
        if entry:
            try:
                # Delete selected text if any
                try:
                    entry.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass  # No selection
                
                # Insert at cursor position
                try:
                    cursor_pos = entry.index("insert")
                except tk.TclError:
                    cursor_pos = 0
                
                entry.insert(cursor_pos, text)
                entry.icursor(cursor_pos + len(text))
                
                logger.debug(f"Ctrl+V paste successful: '{text[:20]}...'")
                return "break"  # Prevent default handling
            except Exception as e:
                logger.debug(f"Ctrl+V insert error: {e}")
        
        return None

    def _show_paste_menu(self, event, widget):
        """Show context menu with paste option."""
        menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white")
        
        def paste_action():
            if pyperclip:
                try:
                    text = pyperclip.paste()
                    if text:
                        # CTkEntry имеет внутренний виджет _entry (tk.Entry)
                        entry = None
                        
                        # Если widget имеет атрибут _entry - это CTkEntry
                        if hasattr(widget, '_entry'):
                            entry = widget._entry
                        # Обычный tk.Entry
                        elif hasattr(widget, 'get') and hasattr(widget, 'icursor'):
                            entry = widget
                        
                        if entry:
                            try:
                                cursor_pos = entry.index("insert")
                            except tk.TclError:
                                try:
                                    cursor_pos = entry.icursor()
                                except tk.TclError:
                                    cursor_pos = len(entry.get())
                            
                            current_text = entry.get()
                            new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
                            entry.delete(0, "end")
                            entry.insert(0, new_text)
                            entry.icursor(cursor_pos + len(text))
                except Exception as e:
                    logger.debug(f"Paste menu error: {e}")
        
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

    def _parse_dsn(self):
        """Parse DSN string and fill connection fields."""
        from ..api.database import parse_dsn

        dsn_string = self.entry_dsn.get().strip()
        if not dsn_string:
            self.lbl_connection_status.configure(
                text="⚠️ Введите DSN строку!",
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
                text="✅ DSN успешно разобран!",
                text_color="green"
            )
        except ValueError as e:
            self.lbl_connection_status.configure(
                text=f"⚠️ Ошибка разбора DSN: {str(e)}",
                text_color="orange"
            )
        except Exception as e:
            self.lbl_connection_status.configure(
                text=f"❌ Ошибка: {str(e)}",
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
                text=f"⚠️ Порт API должен быть числом (получено: '{api_port_text}')",
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
            debug=self.switch_debug.get()
        )
        
        # Update app config
        config.update_app(
            enable_logging=self.switch_logging.get()
        )
        
        try:
            config.save()
        except OSError as e:
            self.lbl_connection_status.configure(
                text=f"❌ Не удалось сохранить настройки: {e}",
                text_color="red"
            )
            return
        
        # Применяем изменения к работающему API (ключи и параметры БД — без перезапуска)
        self._reload_runtime_config()
        
        logger.info("Settings saved")
        self.lbl_connection_status.configure(text="✅ Настройки сохранены", text_color="green")
    
    def _save_and_apply(self):
        """Сохраняет конфиг и применяет его к работающему API."""
        try:
            config.save()
        except OSError as e:
            logger.error(f"Failed to save configuration: {e}")
            self.lbl_connection_status.configure(
                text=f"❌ Не удалось сохранить настройки: {e}",
                text_color="red"
            )
            return
        
        self._reload_runtime_config()
    
    def _reload_runtime_config(self):
        """Применяет текущий конфиг к работающему серверу (hot-reload)."""
        registry = get_registry()
        
        if registry:
            registry.reload(config)
            logger.info("Runtime configuration reloaded")
        
        self._refresh_connections_tree()
    
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
                text="⚠️ Заполните все обязательные поля!",
                text_color="orange"
            )
            return
        
        if not port_text.isdigit():
            self.lbl_connection_status.configure(
                text=f"⚠️ Порт должен быть числом (получено: '{port_text}')",
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
            db.close()
            
            if is_connected:
                self.lbl_connection_status.configure(
                    text="✅ Успешно подключено!",
                    text_color="green"
                )
            else:
                # Показываем причину: неверный пароль / порт закрыт / DNS и т.д.
                reason = db.last_error_message or "причина неизвестна, подробности в app.log"
                self.lbl_connection_status.configure(
                    text=f"❌ Не удалось подключиться: {reason}",
                    text_color="red"
                )
        except ValueError:
            self.lbl_connection_status.configure(
                text="⚠️ Порт должен быть числом!",
                text_color="orange"
            )
        except Exception as e:
            self.lbl_connection_status.configure(
                text=f"❌ Ошибка: {str(e)}",
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
                    text=f"⚠️ Порт API должен быть числом (получено: '{api_port_text}')",
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
                        text="❌ Не удалось запустить API — порт уже занят другим процессом",
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
        
        # Schedule next update
        self.after(2000, self._update_api_status)

    def _update_last_db_error(self):
        """Показывает в статусе причину последней ошибки подключения к БД."""
        registry = get_registry()
        if not registry:
            return
        
        profile = registry.get_default()
        if not profile or not profile.is_db_created:
            return
        
        error = profile.last_error
        if not error:
            return
        
        message = error.get("message") or ""
        hint = error.get("user_hint") or ""
        text = f"❌ БД недоступна: {message}" + (f" — {hint}" if hint else "")
        
        current = self.lbl_connection_status.cget("text")
        if not current.startswith("❌ БД недоступна"):
            self.lbl_connection_status.configure(text=text, text_color="red")

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

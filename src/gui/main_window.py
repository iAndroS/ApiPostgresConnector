"""Main GUI window for ApiPostgresConnector."""
import logging
import threading
from datetime import datetime
from typing import Optional, Any

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

logger = logging.getLogger(__name__)

# Global variable for tray icon
_tray_icon: Optional[Any] = None
_last_activity_time: Optional[datetime] = None


class MainWindow(ctk.CTk):
    """Main application window."""

    def __init__(self, api_server: Optional[object] = None):
        super().__init__()

        self.api_server = api_server

        # Configure window
        gui_config = config.gui
        self.title("ApiPostgresConnector")
        self.geometry(f"{gui_config.get('width', 600)}x{gui_config.get('height', 500)}")
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
            text="ApiPostgresConnector",
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
        self.tabview = ctk.CTkTabview(self, width=560, height=350)
        self.tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Database tab
        self.tab_database = self.tabview.add("База данных")
        self._create_database_tab()

        # API tab
        self.tab_api = self.tabview.add("API")
        self._create_api_tab()

        # API Documentation tab
        self.tab_api_docs = self.tabview.add("Документация API")
        self._create_api_docs_tab()

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
        # Bind right-click menu for all database entry fields
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
            self.entry_port.insert(0, str(parsed.get("port", "")))

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
                text=f"⚠️ Ошибка парсинга: {str(e)}",
                text_color="orange"
            )
        except Exception as e:
            self.lbl_connection_status.configure(
                text=f"❌ Ошибка: {str(e)}",
                text_color="red"
            )

    def _create_database_tab(self):
        """Create database configuration tab."""
        db_config = config.database

        # DSN string
        ctk.CTkLabel(self.tab_database, text="DSN:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_dsn = ctk.CTkEntry(self.tab_database, width=230)
        self.entry_dsn.insert(0, "")
        self.entry_dsn.grid(row=0, column=1, padx=10, pady=10)

        # Parse DSN button
        self.btn_parse_dsn = ctk.CTkButton(
            self.tab_database,
            text="Из DSN",
            width=80,
            command=self._parse_dsn
        )
        self.btn_parse_dsn.grid(row=0, column=2, padx=5, pady=10)

        self.entry_dsn.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_dsn))

        # Host
        ctk.CTkLabel(self.tab_database, text="Хост:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_host = ctk.CTkEntry(self.tab_database, width=300)
        self.entry_host.insert(0, db_config.get("host", "localhost"))
        self.entry_host.grid(row=1, column=1, padx=10, pady=10)

        # Port
        ctk.CTkLabel(self.tab_database, text="Порт:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_port = ctk.CTkEntry(self.tab_database, width=300)
        self.entry_port.insert(0, str(db_config.get("port", 5432)))
        self.entry_port.grid(row=2, column=1, padx=10, pady=10)

        # Database name
        ctk.CTkLabel(self.tab_database, text="База данных:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.entry_dbname = ctk.CTkEntry(self.tab_database, width=300)
        self.entry_dbname.insert(0, db_config.get("database", "zenno_db"))
        self.entry_dbname.grid(row=3, column=1, padx=10, pady=10)

        # User
        ctk.CTkLabel(self.tab_database, text="Пользователь:").grid(row=4, column=0, padx=10, pady=10, sticky="w")
        self.entry_user = ctk.CTkEntry(self.tab_database, width=300)
        self.entry_user.insert(0, db_config.get("user", "postgres"))
        self.entry_user.grid(row=4, column=1, padx=10, pady=10)

        # Password
        ctk.CTkLabel(self.tab_database, text="Пароль:").grid(row=5, column=0, padx=10, pady=10, sticky="w")
        self.entry_password = ctk.CTkEntry(self.tab_database, width=300, show="*")
        self.entry_password.insert(0, db_config.get("password", ""))
        self.entry_password.grid(row=5, column=1, padx=10, pady=10)

        # Bind paste menu (right-click) for all entry fields
        self._setup_paste_functionality()

        # Test connection button
        self.btn_test = ctk.CTkButton(
            self.tab_database,
            text="Проверить подключение",
            command=self._test_connection
        )
        self.btn_test.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

        # Connection status
        self.lbl_connection_status = ctk.CTkLabel(self.tab_database, text="")
        self.lbl_connection_status.grid(row=8, column=0, columnspan=2, padx=10, pady=5)

    def _create_api_tab(self):
        """Create API configuration tab."""
        import secrets
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

        # API Keys
        ctk.CTkLabel(self.tab_api, text="API Keys:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        
        # Get first API key from list for display
        api_keys_list = api_config.get("api_keys", [])
        display_key = api_keys_list[0] if api_keys_list else ""
        
        self.entry_api_key = ctk.CTkEntry(self.tab_api, width=230)
        self.entry_api_key.insert(0, display_key)
        self.entry_api_key.grid(row=3, column=1, padx=10, pady=10)

        # Buttons frame for API key actions
        self.btn_generate_key = ctk.CTkButton(
            self.tab_api,
            text="🔄",
            width=30,
            command=self._generate_api_key
        )
        self.btn_generate_key.grid(row=3, column=2, padx=2, pady=10)
        
        self.btn_copy_key = ctk.CTkButton(
            self.tab_api,
            text="📋",
            width=30,
            command=self._copy_api_key
        )
        self.btn_copy_key.grid(row=3, column=3, padx=2, pady=10)

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
        self.entry_api_key.bind("<Button-3>", lambda e: self._show_paste_menu(e, self.entry_api_key))

    def _create_api_docs_tab(self):
        """Create API documentation tab."""
        # Create scrollable frame for endpoints
        scroll_frame = ctk.CTkScrollableFrame(self.tab_api_docs, width=520, height=320)
        scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Function to copy URL to clipboard
        def copy_to_clipboard(text, button):
            """Copy text to clipboard."""
            if pyperclip:
                try:
                    pyperclip.copy(text)
                    button.configure(text="✅ Скопировано!", text_color="green")
                    self.after(2000, lambda: button.configure(text="📋 Копировать", text_color="white"))
                except Exception:
                    button.configure(text="❌ Ошибка", text_color="red")

        # Get base URL from config
        api_host = getattr(self, 'entry_api_host', None)
        api_port = getattr(self, 'entry_api_port', None)
        if api_host and api_port:
            base_url = f"http://{api_host.get()}:{api_port.get()}"
        else:
            base_url = "http://127.0.0.1:5000"

        # Endpoints list
        endpoints = [
            ("GET", "/api/tables", "Получить список всех таблиц", f"{base_url}/api/tables"),
            ("GET", "/api/table/{name}", "Получить структуру таблицы", f"{base_url}/api/table/"),
            ("GET", "/api/table/{name}/data", "Получить данные из таблицы (пагинация)", f"{base_url}/api/table/users/data?page=1&per_page=10"),
            ("POST", "/api/table/{name}/data", "Добавить запись в таблицу", f"{base_url}/api/table/users/data"),
            ("PUT", "/api/table/{name}/data/{id}", "Обновить запись", f"{base_url}/api/table/users/data/1"),
            ("DELETE", "/api/table/{name}/data/{id}", "Удалить запись", f"{base_url}/api/table/users/data/1"),
            ("GET", "/health", "Проверить здоровье сервиса", f"{base_url}/health"),
        ]

        # Method colors
        method_colors = {
            "GET": "#4CAF50",
            "POST": "#2196F3",
            "PUT": "#FF9800",
            "DELETE": "#F44336"
        }

        for method, path, desc, url in endpoints:
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

            # URL
            ctk.CTkLabel(
                endpoint_frame,
                text=url,
                text_color="#64B5F6",
                font=ctk.CTkFont(size=10)
            ).pack(anchor="w", padx=10, pady=(5, 0))

            # Copy button
            copy_btn = ctk.CTkButton(
                endpoint_frame,
                text="📋 Копировать",
                width=100
            )
            copy_btn.pack(anchor="w", padx=10, pady=(5, 10))
            # Fix closure with proper lambda
            copy_btn.configure(command=lambda u=url, b=copy_btn: copy_to_clipboard(u, b))

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
        # Update database config
        config.update_database(
            host=self.entry_host.get(),
            port=int(self.entry_port.get()),
            database=self.entry_dbname.get(),
            user=self.entry_user.get(),
            password=self.entry_password.get()
        )

        # Update API config - api_keys should be a list
        new_key = self.entry_api_key.get().strip()
        api_keys_list = [new_key] if new_key else []
        
        config.update_api(
            host=self.entry_api_host.get(),
            port=int(self.entry_api_port.get()),
            debug=self.switch_debug.get(),
            api_keys=api_keys_list
        )

        # Update app config
        config._config.setdefault("app", {}).update({
            "enable_logging": self.switch_logging.get()
        })

        config.save()
        logger.info("Settings saved")

    def _generate_api_key(self):
        """Generate new API key."""
        import secrets
        new_key = secrets.token_urlsafe(32)
        self.entry_api_key.delete(0, "end")
        self.entry_api_key.insert(0, new_key)
        logger.info("New API key generated")

    def _copy_api_key(self):
        """Copy API key to clipboard."""
        if pyperclip:
            try:
                api_key = self.entry_api_key.get()
                if api_key:
                    pyperclip.copy(api_key)
                    # Show feedback
                    original_text = self.btn_copy_key.cget("text")
                    self.btn_copy_key.configure(text="✅", text_color="green")
                    self.after(1500, lambda: self.btn_copy_key.configure(text="📋", text_color="white"))
                    logger.info("API key copied to clipboard")
            except Exception as e:
                logger.error(f"Failed to copy API key: {e}")

    def _test_connection(self):
        """Test database connection."""
        from ..api.database import Database

        # Get values from fields
        host = self.entry_host.get()
        port = self.entry_port.get()
        database = self.entry_dbname.get()
        user = self.entry_user.get()
        password = self.entry_password.get()

        # Validation
        if not all([host, port, database, user]):
            self.lbl_connection_status.configure(
                text="⚠️ Заполните все обязательные поля!",
                text_color="orange"
            )
            return

        # Show loading state
        original_text = self.btn_test.cget("text")
        self.btn_test.configure(text="Проверка...", state="disabled")
        self.lbl_connection_status.configure(text="⏳ Подключение...", text_color="gray")
        self.update()

        try:
            port_int = int(port)
            db = Database({
                "host": host,
                "port": port_int,
                "database": database,
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
                self.lbl_connection_status.configure(
                    text="❌ Не удалось подключиться",
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
            self._save_settings()
            if self.api_server:
                self.api_server.start(
                    host=self.entry_api_host.get(),
                    port=int(self.entry_api_port.get())
                )
                self.btn_toggle_api.configure(text="Остановить API")
                self.status_label.configure(text=f"API: Работает на {self.entry_api_host.get()}:{self.entry_api_port.get()}")

    def _update_api_status(self):
        """Periodically update API status."""
        if self.api_server:
            if self.api_server.is_running():
                self.status_label.configure(text="API: Работает")
                self.btn_toggle_api.configure(text="Остановить API")
            else:
                self.status_label.configure(text="API: Не запущен")
                self.btn_toggle_api.configure(text="Запустить API")

        # Schedule next update
        self.after(2000, self._update_api_status)

    def run(self):
        """Start the GUI main loop."""
        self.mainloop()

    def _create_tray_icon(self):
        """Create system tray icon with menu."""
        global _tray_icon
        
        if not PYTRAY_AVAILABLE:
            logger.warning("pystray not available, tray icon disabled")
            return
        
        # Create a simple icon programmatically
        def create_icon_image():
            """Create a simple icon image."""
            img = Image.new('RGB', (64, 64), color='#2d2d2d')
            draw = ImageDraw.Draw(img)
            # Draw a simple database icon
            draw.ellipse([8, 8, 56, 56], outline='#4a9eff', width=3)
            draw.line([32, 20, 32, 44], fill='#4a9eff', width=2)
            draw.ellipse([22, 28, 42, 40], outline='#4a9eff', width=2)
            return img
        
        # Get current status for tooltip
        def get_tooltip_text() -> str:
            """Get tooltip text with current status."""
            global _last_activity_time
            status = "Работает" if (self.api_server and self.api_server.is_running()) else "Не запущен"
            time_str = _last_activity_time.strftime("%Y-%m-%d %H:%M:%S") if _last_activity_time else "N/A"
            return f"ApiPostgresConnector\nСтатус: {status}\nПоследняя активность: {time_str}"
        
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
            pystray.MenuItem("Выйти", on_quit)
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
        """Minimize window to system tray."""
        # Проверяем, что окно минимизировано (iconic state)
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

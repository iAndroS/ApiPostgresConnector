"""Test that exactly replicates main_window.py structure."""
import customtkinter as ctk
import tkinter as tk
import threading
from datetime import datetime

print('=== Exact Replica Test ===', flush=True)

# Simulate config
class MockConfig:
    gui = {"width": 600, "height": 500, "theme": "dark-blue"}
    database = {"host": "localhost", "port": 5432, "database": "mydb", "user": "postgres", "password": ""}
    api = {"host": "127.0.0.1", "port": 5000, "debug": False}
    app = {"minimize_to_tray": False}

config = MockConfig()

# Try pyperclip
try:
    import pyperclip
except ImportError:
    pyperclip = None

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        gui_config = config.gui
        self.title("ApiPostgresConnector")
        self.geometry(f"{gui_config.get('width', 600)}x{gui_config.get('height', 500)}")
        self.resizable(False, False)
        
        theme = gui_config.get("theme", "dark-blue")
        ctk.set_appearance_mode("dark" if "dark" in theme else "light")
        ctk.set_default_color_theme("blue")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._create_header()
        self._create_tabs()
        self._create_footer()
        
        self.after(1000, self._update_api_status)
        
        # Same binding as main app
        self.bind("<Unmap>", lambda e: self._minimize_to_tray())
        
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
    
    def _create_header(self):
        self.header_frame = ctk.CTkFrame(self, height=60)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="ApiPostgresConnector",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="API: Не запущен",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=0, column=2, padx=20, pady=10)
    
    def _create_tabs(self):
        self.tabview = ctk.CTkTabview(self, width=560, height=350)
        self.tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        self.tab_database = self.tabview.add("База данных")
        self._create_database_tab()
    
    def _create_database_tab(self):
        db_config = config.database
        
        ctk.CTkLabel(self.tab_database, text="DSN:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_dsn = ctk.CTkEntry(self.tab_database, width=230)
        self.entry_dsn.insert(0, "")
        self.entry_dsn.grid(row=0, column=1, padx=10, pady=10)
        
        ctk.CTkLabel(self.tab_database, text="Хост:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_host = ctk.CTkEntry(self.tab_database, width=300)
        self.entry_host.insert(0, db_config.get("host", "localhost"))
        self.entry_host.grid(row=1, column=1, padx=10, pady=10)
        
        ctk.CTkLabel(self.tab_database, text="Пароль:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_password = ctk.CTkEntry(self.tab_database, width=300, show="*")
        self.entry_password.insert(0, db_config.get("password", ""))
        self.entry_password.grid(row=2, column=1, padx=10, pady=10)
        
        self._setup_paste_functionality()
    
    def _setup_paste_functionality(self):
        db_entries = [
            self.entry_dsn, self.entry_host, self.entry_password
        ]
        for entry in db_entries:
            entry.bind("<Button-3>", lambda e, w=entry: self._show_paste_menu(e, w))
    
    def _show_paste_menu(self, event, widget):
        menu = tk.Menu(self, tearoff=0, bg="#2b2b2b", fg="white")
        
        def paste_action():
            if pyperclip:
                try:
                    text = pyperclip.paste()
                    if text:
                        entry = widget._entry if hasattr(widget, '_entry') else widget
                        try:
                            cursor_pos = entry.index("insert")
                        except tk.TclError:
                            cursor_pos = len(entry.get())
                        
                        current_text = entry.get()
                        new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
                        entry.delete(0, "end")
                        entry.insert(0, new_text)
                        entry.icursor(cursor_pos + len(text))
                except Exception as e:
                    print(f'Paste menu error: {e}', flush=True)
        
        menu.add_command(label="Вставить", command=paste_action)
        menu.tk_popup(event.x_root, event.y_root)
    
    def _create_footer(self):
        self.footer_frame = ctk.CTkFrame(self, height=60)
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkButton(self.footer_frame, text="Check Results", command=self._check_results).grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkButton(self.footer_frame, text="Close", command=self.destroy).grid(row=0, column=1, padx=10, pady=10)
    
    def _check_results(self):
        print('\n=== Results ===', flush=True)
        print(f'DSN: "{self.entry_dsn.get()}"', flush=True)
        print(f'Host: "{self.entry_host.get()}"', flush=True)
        print(f'Password: "{self.entry_password.get()}"', flush=True)
    
    def _update_api_status(self):
        self.after(2000, self._update_api_status)
    
    def _minimize_to_tray(self):
        pass  # Disabled for test
    
    def _on_close_window(self):
        self.quit()

# Set clipboard
root = MainWindow()
root.clipboard_clear()
root.clipboard_append('REPLICA_TEST')
root.update()
print('Clipboard set to: REPLICA_TEST', flush=True)
print('Please test Ctrl+V in password field', flush=True)

root.mainloop()
print('Test closed', flush=True)

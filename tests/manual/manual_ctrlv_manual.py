"""Manual test for Ctrl+V - run this and try Ctrl+V in the entry field."""
import tkinter as tk
import customtkinter as ctk

# Try to import pyperclip
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
    print("pyperclip available")
except ImportError:
    PYPERCLIP_AVAILABLE = False
    print("pyperclip NOT available")

class TestWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Ctrl+V Manual Test")
        self.geometry("400x300")
        
        # Label
        self.label = ctk.CTkLabel(self, text="Try Ctrl+V in the entry below:")
        self.label.pack(pady=20)
        
        # Entry
        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.pack(pady=10)
        
        # Status
        self.status = ctk.CTkLabel(self, text="Status: waiting...")
        self.status.pack(pady=20)
        
        # Result
        self.result = ctk.CTkLabel(self, text="")
        self.result.pack(pady=10)
        
        # Bind Ctrl+V using bind_all (like main_window.py)
        self.bind_all("<Control-v>", self.on_ctrl_v_bind_all)
        self.bind_all("<Control-V>", self.on_ctrl_v_bind_all)
        print("bind_all registered for <Control-v>")
        
        # Also bind to _entry directly
        if hasattr(self.entry, '_entry'):
            self.entry._entry.bind("<Control-v>", self.on_ctrl_v_entry)
            self.entry._entry.bind("<Control-V>", self.on_ctrl_v_entry)
            print("bind to _entry registered")
        
        # Button to check clipboard
        self.btn = ctk.CTkButton(self, text="Check Clipboard", command=self.check_clipboard)
        self.btn.pack(pady=10)
        
        # Instructions
        self.instructions = ctk.CTkLabel(
            self, 
            text="1. Copy some text to clipboard\n2. Click in entry field\n3. Press Ctrl+V",
            justify="left"
        )
        self.instructions.pack(pady=20)
    
    def on_ctrl_v_bind_all(self, event):
        self.status.configure(text="Status: bind_all Ctrl+V triggered!")
        print(f"bind_all Ctrl+V, widget: {event.widget}")
        
        if not PYPERCLIP_AVAILABLE:
            self.result.configure(text="ERROR: pyperclip not available")
            return "break"
        
        try:
            text = pyperclip.paste()
            self.result.configure(text=f"Clipboard: '{text[:30]}...'")
            
            # Try to insert
            widget = event.widget
            if hasattr(widget, '_entry'):
                entry = widget._entry
            elif hasattr(widget, 'insert'):
                entry = widget
            else:
                self.result.configure(text=f"Widget has no entry: {widget}")
                return "break"
            
            # Insert at cursor
            try:
                cursor_pos = entry.index("insert")
            except:
                cursor_pos = 0
            
            entry.insert(cursor_pos, text)
            self.status.configure(text="Status: PASTE SUCCESSFUL!")
            
        except Exception as e:
            self.result.configure(text=f"Error: {e}")
        
        return "break"
    
    def on_ctrl_v_entry(self, event):
        self.status.configure(text="Status: _entry Ctrl+V triggered!")
        print(f"_entry Ctrl+V, widget: {event.widget}")
        # Don't return break - let bind_all also handle it
        return None
    
    def check_clipboard(self):
        if PYPERCLIP_AVAILABLE:
            text = pyperclip.paste()
            self.result.configure(text=f"Clipboard: '{text[:50]}'")
        else:
            self.result.configure(text="pyperclip not available")

if __name__ == "__main__":
    app = TestWindow()
    print("Window created. Try Ctrl+V in the entry field.")
    app.mainloop()

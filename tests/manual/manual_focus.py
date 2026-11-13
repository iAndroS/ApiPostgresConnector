"""Test focus and keyboard events in CTkEntry."""
import customtkinter as ctk
import tkinter as tk

def test_focus():
    root = ctk.CTk()
    root.title("Focus Test")
    root.geometry("500x400")
    
    # Status label
    status = ctk.CTkLabel(root, text="Click on entry and check focus")
    status.pack(pady=10)
    
    # CTkEntry
    ctk.CTkLabel(root, text="CTkEntry:").pack(pady=5)
    entry = ctk.CTkEntry(root, width=300)
    entry.pack(pady=5)
    
    # Password CTkEntry
    ctk.CTkLabel(root, text="Password CTkEntry:").pack(pady=5)
    pwd_entry = ctk.CTkEntry(root, width=300, show="*")
    pwd_entry.pack(pady=5)
    
    # Native tk.Entry for comparison
    ctk.CTkLabel(root, text="Native tk.Entry:").pack(pady=5)
    native_entry = tk.Entry(root, width=40)
    native_entry.pack(pady=5)
    
    # Focus tracking
    def update_focus_info():
        focused = root.focus_get()
        status.configure(text=f"Focused widget: {focused}")
        root.after(500, update_focus_info)
    
    # Bind focus events
    def on_focus_in(event):
        print(f"Focus IN: {event.widget}")
    
    def on_focus_out(event):
        print(f"Focus OUT: {event.widget}")
    
    # Bind to CTkEntry
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)
    
    # Bind to internal _entry
    if hasattr(entry, '_entry'):
        entry._entry.bind("<FocusIn>", on_focus_in)
        entry._entry.bind("<FocusOut>", on_focus_out)
    
    # Bind keyboard events
    def on_key(event):
        print(f"Key event: {event.keysym} on {event.widget}")
    
    entry.bind("<Key>", on_key)
    if hasattr(entry, '_entry'):
        entry._entry.bind("<Key>", on_key)
    
    # Test Ctrl+V binding
    def on_ctrl_v(event):
        print(f"Ctrl+V on: {event.widget}")
        try:
            clipboard = root.clipboard_get()
            print(f"Clipboard content: {clipboard[:50]}...")
        except:
            print("Clipboard is empty or error")
        return "break"  # Prevent default
    
    # Bind Ctrl+V to internal entry
    if hasattr(entry, '_entry'):
        entry._entry.bind("<Control-v>", on_ctrl_v)
        entry._entry.bind("<Control-V>", on_ctrl_v)
        print("Bound Ctrl+V to internal _entry")
    
    if hasattr(pwd_entry, '_entry'):
        pwd_entry._entry.bind("<Control-v>", on_ctrl_v)
        pwd_entry._entry.bind("<Control-V>", on_ctrl_v)
        print("Bound Ctrl+V to password internal _entry")
    
    # Start focus tracking
    root.after(500, update_focus_info)
    
    print("=== Test Instructions ===")
    print("1. Click on CTkEntry field")
    print("2. Press Ctrl+V to paste")
    print("3. Check console output")
    print("4. Try with password field too")
    
    root.mainloop()

if __name__ == "__main__":
    test_focus()

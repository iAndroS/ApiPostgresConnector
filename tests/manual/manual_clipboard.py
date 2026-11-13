"""Test script to check Ctrl+V functionality in CTkEntry."""
import customtkinter as ctk
import tkinter as tk

def test_native_entry():
    """Test native tk.Entry."""
    root = tk.Tk()
    root.title("Native tk.Entry Test")
    root.geometry("400x200")
    
    # Native Entry
    tk.Label(root, text="Native tk.Entry (Ctrl+V should work):").pack(pady=5)
    entry = tk.Entry(root, width=40)
    entry.pack(pady=5)
    
    # Password field
    tk.Label(root, text="Password field (show='*'):").pack(pady=5)
    pwd_entry = tk.Entry(root, width=40, show="*")
    pwd_entry.pack(pady=5)
    
    root.mainloop()

def test_ctk_entry():
    """Test CTkEntry."""
    root = ctk.CTk()
    root.title("CTkEntry Test")
    root.geometry("400x300")
    
    # CTkEntry
    ctk.CTkLabel(root, text="CTkEntry (Ctrl+V should work):").pack(pady=5)
    entry = ctk.CTkEntry(root, width=300)
    entry.pack(pady=5)
    
    # Password field
    ctk.CTkLabel(root, text="Password field (show='*'):").pack(pady=5)
    pwd_entry = ctk.CTkEntry(root, width=300, show="*")
    pwd_entry.pack(pady=5)
    
    # Debug info
    def print_widget_info():
        print(f"Entry widget: {entry}")
        print(f"Entry has _entry: {hasattr(entry, '_entry')}")
        if hasattr(entry, '_entry'):
            print(f"Internal _entry: {entry._entry}")
        print(f"Pwd entry widget: {pwd_entry}")
        print(f"Pwd entry has _entry: {hasattr(pwd_entry, '_entry')}")
    
    ctk.CTkButton(root, text="Print Widget Info", command=print_widget_info).pack(pady=10)
    
    root.mainloop()

def test_ctk_entry_with_bind():
    """Test CTkEntry with explicit Ctrl+V binding."""
    root = ctk.CTk()
    root.title("CTkEntry with Explicit Bind")
    root.geometry("400x300")
    
    # CTkEntry with explicit bind
    ctk.CTkLabel(root, text="CTkEntry with explicit Ctrl+V bind:").pack(pady=5)
    entry = ctk.CTkEntry(root, width=300)
    entry.pack(pady=5)
    
    # Bind Ctrl+V to the internal entry
    def on_paste(event):
        print(f"Paste event on: {event.widget}")
        try:
            clipboard = root.clipboard_get()
            print(f"Clipboard: {clipboard}")
            # Let default behavior handle it
            return None
        except Exception as e:
            print(f"Error: {e}")
        return None
    
    # Bind to internal _entry widget
    if hasattr(entry, '_entry'):
        entry._entry.bind("<Control-v>", on_paste)
        entry._entry.bind("<Control-V>", on_paste)
        print("Bound to internal _entry")
    
    # Password field
    ctk.CTkLabel(root, text="Password field:").pack(pady=5)
    pwd_entry = ctk.CTkEntry(root, width=300, show="*")
    pwd_entry.pack(pady=5)
    
    if hasattr(pwd_entry, '_entry'):
        pwd_entry._entry.bind("<Control-v>", on_paste)
        pwd_entry._entry.bind("<Control-V>", on_paste)
    
    root.mainloop()

if __name__ == "__main__":
    print("Testing CTkEntry Ctrl+V functionality...")
    print("1. Native tk.Entry")
    print("2. CTkEntry")
    print("3. CTkEntry with explicit bind")
    
    choice = input("Choose test (1/2/3): ").strip()
    
    if choice == "1":
        test_native_entry()
    elif choice == "2":
        test_ctk_entry()
    elif choice == "3":
        test_ctk_entry_with_bind()
    else:
        print("Running CTkEntry test...")
        test_ctk_entry()

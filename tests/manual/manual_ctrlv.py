"""Test script for Ctrl+V functionality."""
import tkinter as tk
import customtkinter as ctk
import pyperclip

# Test CTkEntry with bind_all approach
print("Testing CTkEntry with bind_all...")

# Create test window
root = ctk.CTk()
root.title("Test Ctrl+V")

# Test entries
ctk_entry1 = ctk.CTkEntry(root, width=300)
ctk_entry1.pack(pady=10)
ctk_entry1.insert(0, "Test entry 1")

ctk_entry2 = ctk.CTkEntry(root, width=300)
ctk_entry2.pack(pady=10)
ctk_entry2.insert(0, "Test entry 2")

def on_paste(event):
    """Handle paste event."""
    widget = event.widget
    print(f"Event widget: {widget}, type: {type(widget)}")
    
    # Try to find entry
    entry = None
    if hasattr(widget, '_entry') and widget._entry:
        entry = widget._entry
        print(f"Found _entry: {entry}")
    elif hasattr(widget, 'insert') and hasattr(widget, 'delete'):
        entry = widget
        print(f"Using widget directly: {entry}")
    
    if entry:
        # Get clipboard
        try:
            text = pyperclip.paste()
            print(f"Clipboard text: '{text}'")
            
            if text:
                # Delete selection if any
                try:
                    entry.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                
                # Insert at cursor
                try:
                    pos = entry.index("insert")
                except tk.TclError:
                    pos = 0
                
                entry.insert(pos, text)
                entry.icursor(pos + len(text))
                print(f"Inserted at position {pos}")
                return "break"
        except Exception as e:
            print(f"Error: {e}")
    
    return None

# Method 1: bind_all
root.bind_all("<Control-v>", on_paste)
root.bind_all("<Control-V>", on_paste)
print("bind_all registered")

# Method 2: Direct bind to CTkEntry
ctk_entry1.bind("<Control-v>", on_paste)
ctk_entry1.bind("<Control-V>", on_paste)
ctk_entry2.bind("<Control-v>", on_paste)
ctk_entry2.bind("<Control-V>", on_paste)
print("Direct binds registered")

# Check if _entry exists
print(f"\nctk_entry1._entry: {ctk_entry1._entry}")
print(f"ctk_entry2._entry: {ctk_entry2._entry}")

# Check what events CTkEntry receives
def on_key_event(event):
    print(f"Key event: {event.keysym}, keycode: {event.keycode}")

ctk_entry1.bind("<Key>", on_key_event)
ctk_entry1.bind("<Control-Key-v>", on_key_event)

print("\nStarting test window. Try Ctrl+V in the entries.")
print("Press Ctrl+C in terminal to exit")

# Run
root.mainloop()

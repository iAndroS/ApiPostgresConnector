"""Test if CTkEntry has native Ctrl+V support."""
import tkinter as tk
import customtkinter as ctk
import pyperclip

# Set some clipboard content
pyperclip.copy("Hello from clipboard!")

root = ctk.CTk()
root.title("Test Native Ctrl+V")

label = ctk.CTkLabel(root, text="Copy some text and try Ctrl+V in the entry below")
label.pack(pady=10)

entry = ctk.CTkEntry(root, width=300)
entry.pack(pady=10)
entry.insert(0, "Initial text ")

# Try to check if native binding exists
print("Checking CTkEntry native events...")

# Check internal _entry bindings
if hasattr(entry, '_entry'):
    print(f"_entry widget: {entry._entry}")
    print(f"_entry type: {type(entry._entry)}")
    
    # Check what bindings exist on _entry
    bindings = entry._entry.bind()
    print(f"_entry bindings: {bindings}")
    
    # Check for Control-v
    v_bindings = entry._entry.bind('Control-v')
    print(f"Control-v binding on _entry: {v_bindings}")

print("\nIf Ctrl+V works natively, the text should be inserted.")
print("If not, we'll see an error or nothing will happen.")
print("\nTry Ctrl+V in the entry field now!")

root.mainloop()

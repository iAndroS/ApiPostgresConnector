"""Test CTkEntry internal structure."""
import customtkinter as ctk

root = ctk.CTk()
root.withdraw()  # Hide window

# Create CTkEntry
entry = ctk.CTkEntry(root, width=300)
entry.pack()

# Update to ensure widget is created
root.update()

print("=== CTkEntry Structure Analysis ===")
print(f"CTkEntry widget: {entry}")
print(f"CTkEntry class: {entry.__class__.__name__}")
print(f"Has _entry attribute: {hasattr(entry, '_entry')}")

if hasattr(entry, '_entry'):
    print(f"Internal _entry: {entry._entry}")
    print(f"Internal _entry class: {entry._entry.__class__.__name__}")
    
    # Check bindings on internal entry
    internal_bindings = entry._entry.bind()
    print(f"Internal _entry bindings: {internal_bindings}")
    
    # Check if Ctrl+V is bound
    ctrl_v_bindings = entry._entry.bind("<Control-v>")
    ctrl_V_bindings = entry._entry.bind("<Control-V>")
    print(f"Ctrl+v bindings on internal: {ctrl_v_bindings}")
    print(f"Ctrl+V bindings on internal: {ctrl_V_bindings}")

# Check bindings on CTkEntry itself
ctk_bindings = entry.bind()
print(f"CTkEntry bindings: {ctk_bindings}")

# Check all methods
print("\n=== CTkEntry Methods ===")
methods = [m for m in dir(entry) if not m.startswith('_')]
print(f"Public methods: {methods[:20]}...")

# Check if there's a clipboard method
print(f"\nHas clipboard_get: {hasattr(entry, 'clipboard_get')}")
print(f"Has clipboard_clear: {hasattr(entry, 'clipboard_clear')}")
print(f"Has clipboard_append: {hasattr(entry, 'clipboard_append')}")

# Test password field
pwd_entry = ctk.CTkEntry(root, width=300, show="*")
pwd_entry.pack()
root.update()

print("\n=== Password CTkEntry ===")
print(f"Password entry has _entry: {hasattr(pwd_entry, '_entry')}")
if hasattr(pwd_entry, '_entry'):
    print(f"Password internal _entry show: {pwd_entry._entry.cget('show')}")

root.destroy()
print("\n=== Test Complete ===")

"""Test CTkEntry with explicit Ctrl+V binding."""
import customtkinter as ctk
import tkinter as tk

print('=== CTkEntry Explicit Binding Test ===', flush=True)

root = ctk.CTk()
root.title('CTkEntry Ctrl+V Test')
root.geometry('400x300')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('EXPLICIT_TEST')
root.update()
print('Clipboard set to: EXPLICIT_TEST', flush=True)

# Entry 1: No binding (should work natively)
ctk.CTkLabel(root, text='CTkEntry (no binding):').pack(pady=5)
entry1 = ctk.CTkEntry(root, width=300)
entry1.pack(pady=5)

# Entry 2: With explicit binding on internal _entry
ctk.CTkLabel(root, text='CTkEntry (explicit bind on _entry):').pack(pady=5)
entry2 = ctk.CTkEntry(root, width=300)
entry2.pack(pady=5)

def paste_to_entry(entry):
    """Paste clipboard content to entry."""
    try:
        text = root.clipboard_get()
        print(f'Clipboard: {text}', flush=True)
        # Insert at cursor position
        if hasattr(entry, '_entry'):
            pos = entry._entry.index('insert')
            entry._entry.insert(pos, text)
        else:
            entry.insert('insert', text)
        print('Paste successful', flush=True)
    except Exception as e:
        print(f'Paste error: {e}', flush=True)

# Bind Ctrl+V to internal _entry
if hasattr(entry2, '_entry'):
    entry2._entry.bind('<Control-v>', lambda e: paste_to_entry(entry2) or 'break')
    entry2._entry.bind('<Control-V>', lambda e: paste_to_entry(entry2) or 'break')
    print('Bound Ctrl+V to entry2._entry', flush=True)

# Entry 3: Password field with binding
ctk.CTkLabel(root, text='Password CTkEntry (explicit bind):').pack(pady=5)
entry3 = ctk.CTkEntry(root, width=300, show="*")
entry3.pack(pady=5)

if hasattr(entry3, '_entry'):
    entry3._entry.bind('<Control-v>', lambda e: paste_to_entry(entry3) or 'break')
    entry3._entry.bind('<Control-V>', lambda e: paste_to_entry(entry3) or 'break')
    print('Bound Ctrl+V to entry3._entry', flush=True)

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'Entry 1 (no bind): "{entry1.get()}"', flush=True)
    print(f'Entry 2 (explicit): "{entry2.get()}"', flush=True)
    print(f'Entry 3 (password): "{entry3.get()}"', flush=True)
    
    results = []
    results.append(f'Entry 1: {"OK" if "EXPLICIT_TEST" in entry1.get() else "FAIL"}')
    results.append(f'Entry 2: {"OK" if "EXPLICIT_TEST" in entry2.get() else "FAIL"}')
    results.append(f'Entry 3: {"OK" if "EXPLICIT_TEST" in entry3.get() else "FAIL"}')
    
    lbl.configure(text=' | '.join(results))

ctk.CTkButton(root, text='Check Results', command=check).pack(pady=10)
lbl = ctk.CTkLabel(root, text='')
lbl.pack(pady=5)

ctk.CTkButton(root, text='Close', command=root.destroy).pack(pady=10)

print('\nInstructions:', flush=True)
print('1. Click in each entry field', flush=True)
print('2. Press Ctrl+V', flush=True)
print('3. Click "Check Results"', flush=True)

root.mainloop()
print('Test closed', flush=True)

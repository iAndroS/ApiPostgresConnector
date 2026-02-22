"""Test <<Paste>> virtual event."""
import customtkinter as ctk
import tkinter as tk

print('=== Virtual Paste Event Test ===', flush=True)

root = ctk.CTk()
root.title('Virtual Paste Test')
root.geometry('400x300')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('VIRTUAL_TEST')
root.update()
print('Clipboard set to: VIRTUAL_TEST', flush=True)

# Entry 1: Bind <<Paste>> on internal _entry
ctk.CTkLabel(root, text='CTkEntry (<<Paste>> bind):').pack(pady=5)
entry1 = ctk.CTkEntry(root, width=300)
entry1.pack(pady=5)

def on_paste_virtual(event):
    print(f'<<Paste>> event on: {event.widget}', flush=True)
    try:
        text = root.clipboard_get()
        print(f'Clipboard: {text}', flush=True)
        # Let default behavior work
        return None
    except Exception as e:
        print(f'Error: {e}', flush=True)
        return None

if hasattr(entry1, '_entry'):
    entry1._entry.bind('<<Paste>>', on_paste_virtual)
    print('Bound <<Paste>> to entry1._entry', flush=True)

# Entry 2: Manual paste via Ctrl+V
ctk.CTkLabel(root, text='CTkEntry (Ctrl+V manual):').pack(pady=5)
entry2 = ctk.CTkEntry(root, width=300)
entry2.pack(pady=5)

def manual_paste(event):
    print(f'Ctrl+V on: {event.widget}', flush=True)
    try:
        text = root.clipboard_get()
        print(f'Clipboard: {text}', flush=True)
        # Insert at cursor
        if hasattr(entry2, '_entry'):
            pos = entry2._entry.index('insert')
            entry2._entry.insert(pos, text)
        return 'break'  # Stop propagation
    except Exception as e:
        print(f'Error: {e}', flush=True)
        return None

if hasattr(entry2, '_entry'):
    entry2._entry.bind('<Control-v>', manual_paste)
    entry2._entry.bind('<Control-V>', manual_paste)
    print('Bound Ctrl+V to entry2._entry', flush=True)

# Entry 3: Password field
ctk.CTkLabel(root, text='Password CTkEntry:').pack(pady=5)
entry3 = ctk.CTkEntry(root, width=300, show="*")
entry3.pack(pady=5)

if hasattr(entry3, '_entry'):
    entry3._entry.bind('<Control-v>', manual_paste)
    entry3._entry.bind('<Control-V>', manual_paste)
    print('Bound Ctrl+V to entry3._entry', flush=True)

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'Entry 1: "{entry1.get()}"', flush=True)
    print(f'Entry 2: "{entry2.get()}"', flush=True)
    print(f'Entry 3: "{entry3.get()}"', flush=True)

ctk.CTkButton(root, text='Check Results', command=check).pack(pady=10)
ctk.CTkButton(root, text='Close', command=root.destroy).pack(pady=10)

print('\nInstructions:', flush=True)
print('1. Click in each entry', flush=True)
print('2. Press Ctrl+V', flush=True)
print('3. Click "Check Results"', flush=True)

root.mainloop()
print('Test closed', flush=True)

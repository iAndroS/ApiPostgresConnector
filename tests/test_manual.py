"""Manual test for Ctrl+V - run this and test manually."""
import tkinter as tk
import customtkinter as ctk

print('=== Manual Ctrl+V Test ===', flush=True)
print('Please test Ctrl+V in each entry field', flush=True)
print('Close window when done', flush=True)

root = ctk.CTk()
root.title('Ctrl+V Manual Test')
root.geometry('500x400')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('TEST_CLIPBOARD_123')
root.update()

# Instructions
ctk.CTkLabel(root, text='Clipboard contains: TEST_CLIPBOARD_123', text_color='green').pack(pady=10)
ctk.CTkLabel(root, text='Click in each entry and press Ctrl+V').pack(pady=5)

# Native tk.Entry
ctk.CTkLabel(root, text='Native tk.Entry:').pack(pady=5)
native_entry = tk.Entry(root, width=40)
native_entry.pack(pady=5)

# CTkEntry without binding
ctk.CTkLabel(root, text='CTkEntry (no binding):').pack(pady=5)
ctk_entry = ctk.CTkEntry(root, width=300)
ctk_entry.pack(pady=5)

# CTkEntry with explicit Ctrl+V binding
ctk.CTkLabel(root, text='CTkEntry (with Ctrl+V binding):').pack(pady=5)
ctk_entry_bound = ctk.CTkEntry(root, width=300)
ctk_entry_bound.pack(pady=5)

def handle_paste(entry):
    try:
        text = root.clipboard_get()
        if hasattr(entry, '_entry'):
            pos = entry._entry.index('insert')
            entry._entry.insert(pos, text)
        else:
            entry.insert('insert', text)
    except Exception as e:
        print(f'Paste error: {e}', flush=True)
    return 'break'

if hasattr(ctk_entry_bound, '_entry'):
    ctk_entry_bound._entry.bind('<Control-v>', lambda e: handle_paste(ctk_entry_bound))
    ctk_entry_bound._entry.bind('<Control-V>', lambda e: handle_paste(ctk_entry_bound))

# Password CTkEntry with binding
ctk.CTkLabel(root, text='Password CTkEntry (with Ctrl+V binding):').pack(pady=5)
pwd_entry = ctk.CTkEntry(root, width=300, show="*")
pwd_entry.pack(pady=5)

if hasattr(pwd_entry, '_entry'):
    pwd_entry._entry.bind('<Control-v>', lambda e: handle_paste(pwd_entry))
    pwd_entry._entry.bind('<Control-V>', lambda e: handle_paste(pwd_entry))

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'Native tk.Entry: "{native_entry.get()}"', flush=True)
    print(f'CTkEntry (no bind): "{ctk_entry.get()}"', flush=True)
    print(f'CTkEntry (bound): "{ctk_entry_bound.get()}"', flush=True)
    print(f'Password (bound): "{pwd_entry.get()}"', flush=True)
    
    results = []
    if 'TEST_CLIPBOARD_123' in native_entry.get():
        results.append('Native: OK')
    else:
        results.append('Native: FAIL')
    
    if 'TEST_CLIPBOARD_123' in ctk_entry.get():
        results.append('CTkEntry: OK')
    else:
        results.append('CTkEntry: FAIL')
    
    if 'TEST_CLIPBOARD_123' in ctk_entry_bound.get():
        results.append('CTkEntry (bound): OK')
    else:
        results.append('CTkEntry (bound): FAIL')
    
    if 'TEST_CLIPBOARD_123' in pwd_entry.get():
        results.append('Password: OK')
    else:
        results.append('Password: FAIL')
    
    result_label.configure(text=' | '.join(results))

ctk.CTkButton(root, text='Check Results', command=check).pack(pady=10)
result_label = ctk.CTkLabel(root, text='')
result_label.pack(pady=5)

ctk.CTkButton(root, text='Close', command=root.destroy).pack(pady=10)

root.mainloop()

print('\nTest closed', flush=True)

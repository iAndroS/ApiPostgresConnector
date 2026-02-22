"""Manual paste test with detailed logging."""
import tkinter as tk
import customtkinter as ctk
import sys

print('=== Manual Paste Test ===', flush=True)
print('This test will help diagnose Ctrl+V issues', flush=True)

root = ctk.CTk()
root.title('Ctrl+V Diagnostic Test')
root.geometry('500x400')

# Set clipboard
def set_clipboard():
    root.clipboard_clear()
    root.clipboard_append('CLIPBOARD_TEST_123')
    root.update()
    print('Clipboard set to: CLIPBOARD_TEST_123', flush=True)
    lbl_status.configure(text='Clipboard set! Click in entry and press Ctrl+V')

ctk.CTkButton(root, text='Set Clipboard', command=set_clipboard).pack(pady=10)

# Native Entry
ctk.CTkLabel(root, text='Native tk.Entry:').pack(pady=5)
native_entry = tk.Entry(root, width=50)
native_entry.pack(pady=5)

# CTkEntry
ctk.CTkLabel(root, text='CTkEntry:').pack(pady=5)
ctk_entry = ctk.CTkEntry(root, width=300)
ctk_entry.pack(pady=5)

# Password CTkEntry
ctk.CTkLabel(root, text='Password CTkEntry:').pack(pady=5)
pwd_entry = ctk.CTkEntry(root, width=300, show="*")
pwd_entry.pack(pady=5)

# Status label
lbl_status = ctk.CTkLabel(root, text='Click "Set Clipboard" first')
lbl_status.pack(pady=10)

# Focus info
lbl_focus = ctk.CTkLabel(root, text='Focus: None')
lbl_focus.pack(pady=5)

def update_focus():
    focused = root.focus_get()
    lbl_focus.configure(text=f'Focus: {focused}')
    root.after(200, update_focus)

# Bind keyboard events to see what's happening
def log_key(event):
    print(f'Key: {event.keysym}, State: {event.state}, Widget: {event.widget}', flush=True)

root.bind_all('<Key>', log_key)

# Bind Ctrl+V specifically
def log_ctrl_v(event):
    print(f'Ctrl+V detected on: {event.widget}', flush=True)
    try:
        cb = root.clipboard_get()
        print(f'Clipboard content: {cb}', flush=True)
    except Exception as e:
        print(f'Clipboard error: {e}', flush=True)

root.bind_all('<Control-v>', log_ctrl_v)
root.bind_all('<Control-V>', log_ctrl_v)

# Check button
def check_results():
    print('\n=== Check Results ===', flush=True)
    print(f'Native Entry: "{native_entry.get()}"', flush=True)
    print(f'CTkEntry: "{ctk_entry.get()}"', flush=True)
    print(f'Password Entry: "{pwd_entry.get()}"', flush=True)
    
    results = []
    if 'CLIPBOARD_TEST_123' in native_entry.get():
        results.append('Native: OK')
    else:
        results.append('Native: FAIL')
    
    if 'CLIPBOARD_TEST_123' in ctk_entry.get():
        results.append('CTkEntry: OK')
    else:
        results.append('CTkEntry: FAIL')
    
    if 'CLIPBOARD_TEST_123' in pwd_entry.get():
        results.append('Password: OK')
    else:
        results.append('Password: FAIL')
    
    lbl_status.configure(text=' | '.join(results))

ctk.CTkButton(root, text='Check Results', command=check_results).pack(pady=10)

# Close button
ctk.CTkButton(root, text='Close', command=root.destroy).pack(pady=10)

# Start focus tracking
root.after(200, update_focus)

print('\nInstructions:', flush=True)
print('1. Click "Set Clipboard" button', flush=True)
print('2. Click in each entry field', flush=True)
print('3. Press Ctrl+V', flush=True)
print('4. Click "Check Results"', flush=True)
print('5. Check console for key events', flush=True)

root.mainloop()
print('\nTest closed', flush=True)

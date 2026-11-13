"""Test focus handling in CTkEntry."""
import customtkinter as ctk
import tkinter as tk

print('=== Focus Handling Test ===', flush=True)

root = ctk.CTk()
root.title('Focus Test')
root.geometry('500x400')

# Status
status = ctk.CTkLabel(root, text='Click on entries and check focus')
status.pack(pady=10)

# Focus info
focus_info = ctk.CTkLabel(root, text='Focus: None')
focus_info.pack(pady=5)

# Entry 1
ctk.CTkLabel(root, text='CTkEntry 1:').pack(pady=5)
entry1 = ctk.CTkEntry(root, width=300)
entry1.pack(pady=5)

# Entry 2
ctk.CTkLabel(root, text='CTkEntry 2:').pack(pady=5)
entry2 = ctk.CTkEntry(root, width=300)
entry2.pack(pady=5)

# Password entry
ctk.CTkLabel(root, text='Password CTkEntry:').pack(pady=5)
pwd_entry = ctk.CTkEntry(root, width=300, show="*")
pwd_entry.pack(pady=5)

# Track focus
def update_focus():
    focused = root.focus_get()
    focus_info.configure(text=f'Focus: {focused}')
    root.after(100, update_focus)

# Bind focus events
def on_focus_in(event):
    print(f'Focus IN: {event.widget} (class: {event.widget.__class__.__name__})', flush=True)

def on_focus_out(event):
    print(f'Focus OUT: {event.widget}', flush=True)

# Bind to CTkEntry widgets
for entry in [entry1, entry2, pwd_entry]:
    entry.bind('<FocusIn>', on_focus_in)
    entry.bind('<FocusOut>', on_focus_out)
    
    # Also bind to internal _entry
    if hasattr(entry, '_entry'):
        entry._entry.bind('<FocusIn>', on_focus_in)
        entry._entry.bind('<FocusOut>', on_focus_out)

# Bind keyboard events
def on_key(event):
    print(f'Key: {event.keysym} on {event.widget}', flush=True)

root.bind_all('<Key>', on_key)

# Set clipboard
root.clipboard_clear()
root.clipboard_append('FOCUS_TEST')
root.update()
print('Clipboard set to: FOCUS_TEST', flush=True)

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'Entry 1: "{entry1.get()}"', flush=True)
    print(f'Entry 2: "{entry2.get()}"', flush=True)
    print(f'Password: "{pwd_entry.get()}"', flush=True)

ctk.CTkButton(root, text='Check Results', command=check).pack(pady=10)
ctk.CTkButton(root, text='Close', command=root.destroy).pack(pady=10)

# Start focus tracking
root.after(100, update_focus)

print('\nInstructions:', flush=True)
print('1. Click on each entry field', flush=True)
print('2. Watch console for focus events', flush=True)
print('3. Press Ctrl+V and check if paste works', flush=True)

root.mainloop()
print('Test closed', flush=True)

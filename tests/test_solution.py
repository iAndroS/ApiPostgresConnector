"""Test if Ctrl+V works with visible window and proper focus."""
import customtkinter as ctk
import tkinter as tk

print('=== Visible Window Focus Test ===', flush=True)

root = ctk.CTk()
root.title('Ctrl+V Test')
root.geometry('400x200')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('VISIBLE_TEST')
root.update()
print('Clipboard set to: VISIBLE_TEST', flush=True)

# Create entry
ctk.CTkLabel(root, text='Click in entry and press Ctrl+V:').pack(pady=20)
entry = ctk.CTkEntry(root, width=300)
entry.pack(pady=10)

# Focus tracking
def update_focus():
    focused = root.focus_get()
    lbl.configure(text=f'Focus: {focused}')
    root.after(200, update_focus)

lbl = ctk.CTkLabel(root, text='Focus: None')
lbl.pack(pady=5)

# Check button
def check():
    text = entry.get()
    print(f'Entry content: "{text}"', flush=True)
    if 'VISIBLE_TEST' in text:
        print('SUCCESS!', flush=True)
        result.configure(text='SUCCESS!', text_color='green')
    else:
        print('FAILED', flush=True)
        result.configure(text='FAILED', text_color='red')

ctk.CTkButton(root, text='Check', command=check).pack(pady=5)
result = ctk.CTkLabel(root, text='')
result.pack(pady=5)

# Auto-close after 15 seconds
def auto_close():
    print('\nAuto-close triggered', flush=True)
    check()
    root.destroy()

root.after(15000, auto_close)

root.after(200, update_focus)
print('Window opened. Please test Ctrl+V.', flush=True)
root.mainloop()

"""Test paste with visible window."""
import customtkinter as ctk
import tkinter as tk

print('Starting test...', flush=True)

# Create a simple test
root = ctk.CTk()
root.title('Paste Test')
root.geometry('400x200')

# Add test text to clipboard
root.clipboard_clear()
root.clipboard_append('TEST_PASTE_TEXT')
root.update()

print('Clipboard set to: TEST_PASTE_TEXT', flush=True)

# Create entry
ctk.CTkLabel(root, text='Click in entry and press Ctrl+V:').pack(pady=20)
entry = ctk.CTkEntry(root, width=300)
entry.pack(pady=10)

# Result label
result = ctk.CTkLabel(root, text='')
result.pack(pady=10)

# Check button
def check_paste():
    text = entry.get()
    print(f'Entry content: "{text}"', flush=True)
    if 'TEST_PASTE_TEXT' in text:
        result.configure(text='SUCCESS: Paste works!', text_color='green')
        print('SUCCESS: Paste works!', flush=True)
    else:
        result.configure(text='FAILED: Paste did not work', text_color='red')
        print('FAILED: Paste did not work', flush=True)

ctk.CTkButton(root, text='Check Result', command=check_paste).pack(pady=10)

# Auto-check after 10 seconds
def auto_check():
    print('Auto-check triggered', flush=True)
    check_paste()
    root.destroy()

root.after(15000, auto_check)

print('Test window opened. Please try Ctrl+V...', flush=True)
root.mainloop()

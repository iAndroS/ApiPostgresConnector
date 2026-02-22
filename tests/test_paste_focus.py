"""Test paste with visible window and focus."""
import tkinter as tk
import customtkinter as ctk

print('Starting test with visible window...', flush=True)

# Test with visible window
root = ctk.CTk()
root.title('Paste Test')
root.geometry('400x300')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('TEST_CLIPBOARD')
root.update()
print('Clipboard set', flush=True)

# Create entries
ctk.CTkLabel(root, text='Native tk.Entry:').pack(pady=5)
native_entry = tk.Entry(root, width=40)
native_entry.pack(pady=5)

ctk.CTkLabel(root, text='CTkEntry:').pack(pady=5)
ctk_entry = ctk.CTkEntry(root, width=300)
ctk_entry.pack(pady=5)

# Status
status = ctk.CTkLabel(root, text='Click in entry and press Ctrl+V')
status.pack(pady=20)

# Test button
def test_paste():
    native_text = native_entry.get()
    ctk_text = ctk_entry.get()
    
    print(f'\n=== Results ===', flush=True)
    print(f'Native Entry: "{native_text}"', flush=True)
    print(f'CTkEntry: "{ctk_text}"', flush=True)
    
    native_ok = 'TEST_CLIPBOARD' in native_text
    ctk_ok = 'TEST_CLIPBOARD' in ctk_text
    
    print(f'Native paste: {"OK" if native_ok else "FAIL"}', flush=True)
    print(f'CTkEntry paste: {"OK" if ctk_ok else "FAIL"}', flush=True)
    
    status.configure(text=f'Native: {"OK" if native_ok else "FAIL"}, CTkEntry: {"OK" if ctk_ok else "FAIL"}')

ctk.CTkButton(root, text='Test Results', command=test_paste).pack(pady=10)

# Auto-test after 10 seconds
def auto_test():
    print('\nAuto-test triggered...', flush=True)
    test_paste()
    root.destroy()

root.after(12000, auto_test)

print('Window opened. Please test Ctrl+V in both entries.', flush=True)
root.mainloop()
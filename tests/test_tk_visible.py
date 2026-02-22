"""Test Ctrl+V in visible tk.Entry window."""
import tkinter as tk

print('=== Visible tk.Entry Test ===', flush=True)

root = tk.Tk()
root.title('tk.Entry Ctrl+V Test')
root.geometry('400x200')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('TK_TEST')
root.update()
print('Clipboard set to: TK_TEST', flush=True)

# Create entry
tk.Label(root, text='Click in entry and press Ctrl+V:').pack(pady=20)
entry = tk.Entry(root, width=40)
entry.pack(pady=10)

# Check button
def check():
    text = entry.get()
    print(f'Entry content: "{text}"', flush=True)
    if 'TK_TEST' in text:
        print('SUCCESS!', flush=True)
        lbl.configure(text='SUCCESS!', fg='green')
    else:
        print('FAILED', flush=True)
        lbl.configure(text='FAILED', fg='red')

tk.Button(root, text='Check', command=check).pack(pady=5)
lbl = tk.Label(root, text='')
lbl.pack(pady=5)

# Auto-close after 15 seconds
def auto_close():
    print('\nAuto-close triggered', flush=True)
    check()
    root.destroy()

root.after(15000, auto_close)

print('Window opened. Please test Ctrl+V.', flush=True)
root.mainloop()

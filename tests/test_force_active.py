"""Test Ctrl+V with forced window activation."""
import tkinter as tk
import time

print('=== Forced Activation Test ===', flush=True)

root = tk.Tk()
root.title('Forced Activation Test')
root.geometry('400x200')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('FORCE_TEST')
root.update()
print('Clipboard set to: FORCE_TEST', flush=True)

# Create entry
tk.Label(root, text='Entry field:').pack(pady=10)
entry = tk.Entry(root, width=40)
entry.pack(pady=10)

# Force focus
def force_focus():
    root.deiconify()
    root.lift()
    root.focus_force()
    entry.focus_set()
    root.update()
    print(f'Focus: {root.focus_get()}', flush=True)

# Check button
def check():
    text = entry.get()
    print(f'Entry content: "{text}"', flush=True)
    if 'FORCE_TEST' in text:
        print('SUCCESS!', flush=True)
        lbl.configure(text='SUCCESS!', fg='green')
    else:
        print('FAILED', flush=True)
        lbl.configure(text='FAILED', fg='red')

tk.Button(root, text='Check', command=check).pack(pady=5)
lbl = tk.Label(root, text='')
lbl.pack(pady=5)

# Force focus button
tk.Button(root, text='Force Focus', command=force_focus).pack(pady=5)

# Auto-test after 10 seconds
def auto_test():
    print('\nAuto-test triggered', flush=True)
    check()
    root.destroy()

root.after(12000, auto_test)

# Initial focus
root.after(100, force_focus)

print('Window opened. Please test Ctrl+V.', flush=True)
root.mainloop()

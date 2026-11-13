"""Test Ctrl+V in pure tkinter."""
import tkinter as tk

print('=== Pure Tkinter Test ===', flush=True)

root = tk.Tk()
root.title('Pure Tkinter Ctrl+V Test')
root.geometry('400x200')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('TKINTER_TEST')
root.update()
print('Clipboard set to: TKINTER_TEST', flush=True)

# Create entry
tk.Label(root, text='Click in entry and press Ctrl+V:').pack(pady=20)
entry = tk.Entry(root, width=40)
entry.pack(pady=10)

# Bind events
def on_paste(event):
    print(f'Paste event on: {event.widget}', flush=True)
    return None  # Allow default behavior

entry.bind('<<Paste>>', on_paste)

# Check button
def check():
    text = entry.get()
    print(f'Entry content: "{text}"', flush=True)
    if 'TKINTER_TEST' in text:
        print('SUCCESS: Ctrl+V works!', flush=True)
        lbl.configure(text='SUCCESS!', fg='green')
    else:
        print('FAILED: Ctrl+V did not work', flush=True)
        lbl.configure(text='FAILED', fg='red')

tk.Button(root, text='Check Result', command=check).pack(pady=10)
lbl = tk.Label(root, text='')
lbl.pack(pady=5)

# Close button
tk.Button(root, text='Close', command=root.destroy).pack(pady=10)

print('Window opened. Please test Ctrl+V.', flush=True)
root.mainloop()
print('Test closed', flush=True)

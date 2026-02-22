"""Automatic paste test."""
import customtkinter as ctk
import tkinter as tk

print('Starting test...', flush=True)

# Create a simple test
root = ctk.CTk()
root.withdraw()  # Hidden

# Add test text to clipboard
root.clipboard_clear()
root.clipboard_append('TEST_PASTE_TEXT')
root.update()

print('Clipboard set', flush=True)

# Create entry
entry = ctk.CTkEntry(root)
entry.pack()
root.update()

print('Entry created', flush=True)
print(f'Entry has _entry: {hasattr(entry, "_entry")}', flush=True)

# Focus on entry
entry.focus_set()
root.update()

print('Focus set, simulating paste...', flush=True)

# Simulate <<Paste>> event on internal entry
if hasattr(entry, '_entry'):
    entry._entry.event_generate('<<Paste>>')
    root.update()

# Check result
text = entry.get()
print(f'Entry content: "{text}"', flush=True)
if 'TEST_PASTE_TEXT' in text:
    print('SUCCESS: Paste works!', flush=True)
else:
    print('FAILED: Paste did not work', flush=True)

root.destroy()
print('Test complete', flush=True)

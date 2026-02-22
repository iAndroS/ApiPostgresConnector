"""Test paste with native tk.Entry vs CTkEntry."""
import tkinter as tk
import customtkinter as ctk

print('Starting comparison test...', flush=True)

# Test 1: Native tk.Entry
print('\n=== Test 1: Native tk.Entry ===', flush=True)
root1 = tk.Tk()
root1.withdraw()

root1.clipboard_clear()
root1.clipboard_append('NATIVE_TEST')
root1.update()

native_entry = tk.Entry(root1)
native_entry.pack()
root1.update()

native_entry.focus_set()
root1.update()

native_entry.event_generate('<<Paste>>')
root1.update()

native_text = native_entry.get()
print(f'Native Entry content: "{native_text}"', flush=True)
print(f'Native paste works: {"NATIVE_TEST" in native_text}', flush=True)

root1.destroy()

# Test 2: CTkEntry
print('\n=== Test 2: CTkEntry ===', flush=True)
root2 = ctk.CTk()
root2.withdraw()

root2.clipboard_clear()
root2.clipboard_append('CTK_TEST')
root2.update()

ctk_entry = ctk.CTkEntry(root2)
ctk_entry.pack()
root2.update()

ctk_entry.focus_set()
root2.update()

print(f'CTkEntry has _entry: {hasattr(ctk_entry, "_entry")}', flush=True)

if hasattr(ctk_entry, '_entry'):
    ctk_entry._entry.focus_set()
    root2.update()
    ctk_entry._entry.event_generate('<<Paste>>')
    root2.update()

ctk_text = ctk_entry.get()
print(f'CTkEntry content: "{ctk_text}"', flush=True)
print(f'CTkEntry paste works: {"CTK_TEST" in ctk_text}', flush=True)

root2.destroy()

print('\n=== Summary ===', flush=True)
print(f'Native tk.Entry paste: {"WORKS" if "NATIVE_TEST" in native_text else "FAILS"}', flush=True)
print(f'CTkEntry paste: {"WORKS" if "CTK_TEST" in ctk_text else "FAILS"}', flush=True)
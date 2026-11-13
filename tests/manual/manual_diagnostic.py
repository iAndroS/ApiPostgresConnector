"""Comprehensive diagnostic test for Ctrl+V in CTkEntry."""
import customtkinter as ctk
import tkinter as tk

print('=== Comprehensive Diagnostic Test ===', flush=True)

results = []

# Test 1: Check if clipboard works
print('\n--- Test 1: Clipboard ---', flush=True)
root = ctk.CTk()
root.withdraw()

try:
    root.clipboard_clear()
    root.clipboard_append('TEST123')
    root.update()
    content = root.clipboard_get()
    if content == 'TEST123':
        print('Clipboard: OK', flush=True)
        results.append('Clipboard: OK')
    else:
        print(f'Clipboard: FAIL (got "{content}")', flush=True)
        results.append('Clipboard: FAIL')
except Exception as e:
    print(f'Clipboard: FAIL ({e})', flush=True)
    results.append(f'Clipboard: FAIL ({e})')

# Test 2: Check CTkEntry structure
print('\n--- Test 2: CTkEntry Structure ---', flush=True)
entry = ctk.CTkEntry(root)
entry.pack()
root.update()

if hasattr(entry, '_entry'):
    print(f'CTkEntry has _entry: OK', flush=True)
    results.append('_entry attribute: OK')
    
    # Check if _entry is tk.Entry
    if isinstance(entry._entry, tk.Entry):
        print('_entry is tk.Entry: OK', flush=True)
        results.append('_entry type: OK')
    else:
        print(f'_entry type: {type(entry._entry)}', flush=True)
        results.append(f'_entry type: {type(entry._entry).__name__}')
else:
    print('CTkEntry has _entry: FAIL', flush=True)
    results.append('_entry attribute: FAIL')

# Test 3: Check bindings on _entry
print('\n--- Test 3: Default Bindings ---', flush=True)
if hasattr(entry, '_entry'):
    bindings = entry._entry.bind()
    print(f'Default bindings on _entry: {bindings}', flush=True)
    results.append(f'Default bindings: {len(bindings)}')
    
    # Check for <<Paste>> binding
    paste_bind = entry._entry.bind('<<Paste>>')
    print(f'<<Paste>> binding: "{paste_bind}"', flush=True)
    
    # Check for Ctrl+V binding
    ctrl_v_bind = entry._entry.bind('<Control-v>')
    print(f'<Control-v> binding: "{ctrl_v_bind}"', flush=True)

# Test 4: Try to manually trigger paste
print('\n--- Test 4: Manual Paste Trigger ---', flush=True)
root.clipboard_clear()
root.clipboard_append('MANUAL_TEST')
root.update()

if hasattr(entry, '_entry'):
    entry._entry.focus_set()
    root.update()
    
    # Try event_generate
    try:
        entry._entry.event_generate('<<Paste>>')
        root.update()
        text = entry.get()
        if 'MANUAL_TEST' in text:
            print('Manual <<Paste>>: OK', flush=True)
            results.append('Manual <<Paste>>: OK')
        else:
            print(f'Manual <<Paste>>: FAIL (got "{text}")', flush=True)
            results.append('Manual <<Paste>>: FAIL')
    except Exception as e:
        print(f'Manual <<Paste>>: FAIL ({e})', flush=True)
        results.append(f'Manual <<Paste>>: FAIL ({e})')

# Test 5: Try direct insert
print('\n--- Test 5: Direct Insert ---', flush=True)
try:
    entry2 = ctk.CTkEntry(root)
    entry2.pack()
    root.update()
    
    if hasattr(entry2, '_entry'):
        entry2._entry.insert(0, 'DIRECT_INSERT')
        text = entry2.get()
        if 'DIRECT_INSERT' in text:
            print('Direct insert: OK', flush=True)
            results.append('Direct insert: OK')
        else:
            print(f'Direct insert: FAIL (got "{text}")', flush=True)
            results.append('Direct insert: FAIL')
except Exception as e:
    print(f'Direct insert: FAIL ({e})', flush=True)
    results.append(f'Direct insert: FAIL ({e})')

# Test 6: Check if focus works
print('\n--- Test 6: Focus ---', flush=True)
try:
    entry3 = ctk.CTkEntry(root)
    entry3.pack()
    root.update()
    
    entry3._entry.focus_set()
    root.update()
    
    focused = root.focus_get()
    if focused == entry3._entry:
        print('Focus on _entry: OK', flush=True)
        results.append('Focus: OK')
    else:
        print(f'Focus: FAIL (focused on {focused})', flush=True)
        results.append(f'Focus: FAIL ({focused})')
except Exception as e:
    print(f'Focus: FAIL ({e})', flush=True)
    results.append(f'Focus: FAIL ({e})')

root.destroy()

# Summary
print('\n=== Summary ===', flush=True)
for r in results:
    print(f'  - {r}', flush=True)

print('\n=== Conclusion ===', flush=True)
if 'Manual <<Paste>>: FAIL' in results:
    print('<<Paste>> event does not work automatically', flush=True)
    print('Need to bind Ctrl+V manually and handle paste', flush=True)
else:
    print('<<Paste>> event works', flush=True)

"""Diagnostic test for Ctrl+V issue in EXE build."""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import tkinter as tk
import customtkinter as ctk

print("=" * 60)
print("Ctrl+V Diagnostic Test")
print("=" * 60)

# Test 1: Check pyperclip availability
print("\n[TEST 1] Checking pyperclip...")
try:
    import pyperclip
    print(f"  pyperclip imported: {pyperclip}")
    print(f"  pyperclip.__file__: {getattr(pyperclip, '__file__', 'N/A')}")
    
    # Test clipboard read
    test_text = "TEST_CLIPBOARD_123"
    pyperclip.copy(test_text)
    result = pyperclip.paste()
    if result == test_text:
        print(f"  Clipboard read/write: OK")
    else:
        print(f"  Clipboard read/write: FAILED (expected '{test_text}', got '{result}')")
except ImportError as e:
    print(f"  pyperclip import FAILED: {e}")
    pyperclip = None

# Test 2: Check CTkEntry structure
print("\n[TEST 2] Checking CTkEntry structure...")
root = ctk.CTk()
root.withdraw()  # Hide window

entry = ctk.CTkEntry(root)
entry.pack()

# Check internal structure
print(f"  CTkEntry has _entry: {hasattr(entry, '_entry')}")
if hasattr(entry, '_entry'):
    print(f"  _entry type: {type(entry._entry)}")
    print(f"  _entry is tk.Entry: {isinstance(entry._entry, tk.Entry)}")

# Test 3: Check event binding
print("\n[TEST 3] Checking event binding...")

events_received = []

def on_ctrl_v(event):
    events_received.append(('bind_all', event.widget))
    print(f"  bind_all received Ctrl+V, widget: {event.widget}")
    return "break"

def on_ctrl_v_entry(event):
    events_received.append(('bind_entry', event.widget))
    print(f"  bind to _entry received Ctrl+V, widget: {event.widget}")
    return "break"

# Bind to root with bind_all
root.bind_all("<Control-v>", on_ctrl_v)
root.bind_all("<Control-V>", on_ctrl_v)

# Bind to internal _entry
if hasattr(entry, '_entry'):
    entry._entry.bind("<Control-v>", on_ctrl_v_entry)
    entry._entry.bind("<Control-V>", on_ctrl_v_entry)

print(f"  bind_all registered: True")
print(f"  bind to _entry registered: {hasattr(entry, '_entry')}")

# Test 4: Simulate key event
print("\n[TEST 4] Simulating Ctrl+V event...")

# Focus the entry
entry.focus_set()
entry._entry.focus_set()

# Generate event
root.update()
try:
    # Try generating event on _entry
    entry._entry.event_generate("<Control-v>")
    root.update()
    print(f"  Events received: {events_received}")
except Exception as e:
    print(f"  Event generation error: {e}")

# Test 5: Check focus_get
print("\n[TEST 5] Checking focus_get...")
focused = root.focus_get()
print(f"  Current focus: {focused}")
print(f"  Is _entry focused: {focused == entry._entry}")

# Test 6: Check CTkEntry native paste
print("\n[TEST 6] Checking CTkEntry native paste...")
if pyperclip:
    pyperclip.copy("NATIVE_TEST")
    entry.delete(0, "end")
    entry._entry.focus_set()
    root.update()
    
    # Try to check if CTkEntry has native binding
    bindings = entry._entry.bind()
    ctrl_v_bindings = entry._entry.bind("<Control-v>")
    print(f"  _entry all bindings count: {len(bindings)}")
    print(f"  _entry <Control-v> bindings: {ctrl_v_bindings}")

root.destroy()

print("\n" + "=" * 60)
print("Diagnostic complete")
print("=" * 60)

# Summary
print("\n[SUMMARY]")
print("1. pyperclip: ", "OK" if pyperclip else "MISSING")
print("2. CTkEntry._entry: ", "EXISTS" if hasattr(entry, '_entry') else "MISSING")
print("3. bind_all: ", "TESTED")
print("4. Event propagation: ", "CHECK LOGS ABOVE")

"""Diagnostic script to test CTkEntry standard paste behavior."""
import sys
import tkinter as tk
import customtkinter as ctk

print("=" * 60)
print("TEST: CTkEntry standard paste behavior")
print("=" * 60)

# Test if CTkEntry supports standard paste
root = tk.Tk()
root.title("Paste Test")
root.geometry("400x200")

# Test pyperclip
import pyperclip
pyperclip.copy("TEST_PASTE_TEXT")
print(f"Clipboard set to: {pyperclip.paste()}")

# Create CTkEntry
entry1 = ctk.CTkEntry(root, width=300)
entry1.pack(pady=20)
entry1.insert(0, "Click here and press Ctrl+V")

# Create standard tk.Entry for comparison
entry2 = tk.Entry(root, width=40)
entry2.pack(pady=20)
entry2.insert(0, "Standard Entry - try Ctrl+V here too")

# Label for results
label = tk.Label(root, text="After pasting, click 'Check Results'")
label.pack(pady=10)

def check_results():
    val1 = entry1.get()
    val2 = entry2.get()
    print(f"\nCTkEntry value: {val1}")
    print(f"tk.Entry value: {val2}")
    if "TEST_PASTE_TEXT" in val1:
        print("[OK] CTkEntry paste WORKS!")
    else:
        print("[FAIL] CTkEntry paste DOES NOT WORK")
    if "TEST_PASTE_TEXT" in val2:
        print("[OK] tk.Entry paste WORKS!")
    else:
        print("[FAIL] tk.Entry paste DOES NOT WORK")

btn = tk.Button(root, text="Check Results", command=check_results)
btn.pack(pady=10)

# Auto-close after 30 seconds
root.after(30000, root.quit)

print("\nPlease test manually:")
print("1. Click on CTkEntry field")
print("2. Press Ctrl+V")
print("3. Click 'Check Results'")
print("\nWindow will auto-close in 30 seconds...")

root.mainloop()

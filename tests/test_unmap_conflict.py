"""Test Ctrl+V with Unmap binding like in main application."""
import customtkinter as ctk
import tkinter as tk

print('=== Unmap Binding Conflict Test ===', flush=True)

root = ctk.CTk()
root.title('Unmap Conflict Test')
root.geometry('600x400')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('UNMAP_TEST')
root.update()
print('Clipboard set to: UNMAP_TEST', flush=True)

# Create TabView
tabview = ctk.CTkTabview(root, width=560, height=350)
tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

# Database tab
tab_database = tabview.add("База данных")

# Create entries
ctk.CTkLabel(tab_database, text="Пароль:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
entry_password = ctk.CTkEntry(tab_database, width=300, show="*")
entry_password.insert(0, "")
entry_password.grid(row=0, column=1, padx=10, pady=10)

# Status
status = ctk.CTkLabel(root, text='Click in entry and press Ctrl+V')
status.grid(row=1, column=0, pady=10)

# Add Unmap binding like in main app
def on_unmap(event):
    print(f'Unmap event: {event.widget}', flush=True)

root.bind("<Unmap>", on_unmap)

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'Password: "{entry_password.get()}"', flush=True)
    
    if 'UNMAP_TEST' in entry_password.get():
        status.configure(text='SUCCESS: Ctrl+V works with Unmap binding!')
        print('SUCCESS', flush=True)
    else:
        status.configure(text='FAILED: Ctrl+V does not work')
        print('FAILED', flush=True)

ctk.CTkButton(root, text='Check Results', command=check).grid(row=2, column=0, pady=5)
ctk.CTkButton(root, text='Close', command=root.destroy).grid(row=3, column=0, pady=5)

print('Window opened. Please test Ctrl+V with Unmap binding.', flush=True)
root.mainloop()
print('Test closed', flush=True)

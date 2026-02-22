"""Test Ctrl+V with TabView like in main application."""
import customtkinter as ctk
import tkinter as tk

print('=== TabView Ctrl+V Test ===', flush=True)

root = ctk.CTk()
root.title('TabView Test')
root.geometry('600x400')

# Set clipboard
root.clipboard_clear()
root.clipboard_append('TABVIEW_TEST')
root.update()
print('Clipboard set to: TABVIEW_TEST', flush=True)

# Create TabView like in main app
tabview = ctk.CTkTabview(root, width=560, height=350)
tabview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

# Database tab
tab_database = tabview.add("База данных")

# Create entries like in main app
ctk.CTkLabel(tab_database, text="DSN:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
entry_dsn = ctk.CTkEntry(tab_database, width=230)
entry_dsn.insert(0, "")
entry_dsn.grid(row=0, column=1, padx=10, pady=10)

ctk.CTkLabel(tab_database, text="Хост:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
entry_host = ctk.CTkEntry(tab_database, width=300)
entry_host.insert(0, "localhost")
entry_host.grid(row=1, column=1, padx=10, pady=10)

ctk.CTkLabel(tab_database, text="Пароль:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
entry_password = ctk.CTkEntry(tab_database, width=300, show="*")
entry_password.insert(0, "")
entry_password.grid(row=2, column=1, padx=10, pady=10)

# Status
status = ctk.CTkLabel(root, text='Click in entry and press Ctrl+V')
status.grid(row=1, column=0, pady=10)

# Check button
def check():
    print('\n=== Results ===', flush=True)
    print(f'DSN: "{entry_dsn.get()}"', flush=True)
    print(f'Host: "{entry_host.get()}"', flush=True)
    print(f'Password: "{entry_password.get()}"', flush=True)
    
    results = []
    if 'TABVIEW_TEST' in entry_dsn.get():
        results.append('DSN: OK')
    else:
        results.append('DSN: FAIL')
    
    if 'TABVIEW_TEST' in entry_host.get():
        results.append('Host: OK')
    else:
        results.append('Host: FAIL')
    
    if 'TABVIEW_TEST' in entry_password.get():
        results.append('Password: OK')
    else:
        results.append('Password: FAIL')
    
    status.configure(text=' | '.join(results))

ctk.CTkButton(root, text='Check Results', command=check).grid(row=2, column=0, pady=5)
ctk.CTkButton(root, text='Close', command=root.destroy).grid(row=3, column=0, pady=5)

print('Window opened. Please test Ctrl+V in TabView entries.', flush=True)
root.mainloop()
print('Test closed', flush=True)

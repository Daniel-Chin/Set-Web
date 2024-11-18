import tkinter as tk
import tkinter.ttk as ttk

def disableIf(button: tk.Button | ttk.Button, condition: bool):
    if condition:
        button.config(state=tk.DISABLED)
    else:
        if button.cget('state').string == tk.DISABLED:
            button.config(state=tk.NORMAL)

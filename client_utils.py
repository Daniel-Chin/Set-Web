from __future__ import annotations

import time

import tkinter as tk
import tkinter.ttk as ttk

def getState(widget: tk.Widget):
    s = widget.cget('state')
    try:
        return s.string
    except AttributeError:
        return s

def disableIf(button: tk.Button | ttk.Button, condition: bool):
    if condition:
        button.config(state=tk.DISABLED)
    else:
        if getState(button) == tk.DISABLED:
            button.config(state=tk.NORMAL)

class ServerClock:
    def __init__(self):
        self.offset = 0.0
    
    def get(self):
        return time.time() + self.offset
    
    def onReceiveServerTime(self, server_time: float):
        offset = server_time - time.time()
        self.offset = max(self.offset, offset)

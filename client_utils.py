from __future__ import annotations

import typing as tp
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

class Pinger:
    def __init__(
        self, ping: tp.Callable[[], None], interval: float = 2.0, 
    ):
        self.ping = ping
        self.interval = interval
        self.last_is_ping_not_pong = False
        self.last_png_time = 0.0
    
    def poll(self):
        if self.last_is_ping_not_pong:
            return
        if time.time() - self.last_png_time >= self.interval:
            self.last_is_ping_not_pong = True
            self.last_png_time = time.time()
            self.ping()
    
    def onPong(self):
        self.last_is_ping_not_pong = False
        rtl = time.time() - self.last_png_time
        self.last_png_time += rtl
        return rtl

import os
import socket

import tkinter as tk
from tkinter import ttk

class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Web Set")

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    root = Root()
    root.mainloop()

if __name__ == "__main__":
    main()

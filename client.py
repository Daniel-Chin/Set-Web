import os

import tkinter as tk
from tkinter import ttk

class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Set Game")
        self.geometry("800x600")  # Set the window size
        
        self.label = ttk.Label(self, text="Welcome to the Set Game!", font=("Arial", 16))
        self.label.pack(pady=20)
        
        self.start_button = ttk.Button(self, text="Start Game", command=self.start_game)
        self.start_button.pack(pady=10)

        self.quit_button = ttk.Button(self, text="Quit", command=self.quit)
        self.quit_button.pack(pady=10)

    def start_game(self):
        self.label.config(text="Game Started! Looking for Sets...")

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    root = Root()
    root.mainloop()

if __name__ == "__main__":
    main()

import typing as tp
import os
import socket
from contextlib import contextmanager
import gzip
import json
from threading import Thread, Lock

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

PADX = 5
PADY = 5

UpdateGamestateEvent = tp.Callable[[Gamestate], None]
UpdateUUIDEvent = tp.Callable[[str], None]
ArglessEvent = tp.Callable[[], None]
SubmitEventFunc = tp.Callable[[tp.Dict], None]

def EventsIn(sock: socket.socket):
    buf = b''
    while True:
        data = sock.recv(1024)
        if not data:
            break
        buf += data
        while b'\x00' in buf:
            packet, buf = buf.split(b'\x00', 1)
            do_stop = yield json.loads(gzip.decompress(packet).decode())
            if do_stop is not None:
                return

@contextmanager
def NetworkClient(
    host: str, port: int,
    onUpdateGamestate: UpdateGamestateEvent, 
    onUpdateUUID: UpdateUUIDEvent, 
    onDisconnect: ArglessEvent,
):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        print(f'Connecting to {host}:{port}... ', end='', flush=True)
        sock.connect((host, port))
        print('ok')

        def write(event: tp.Dict):
            data = gzip.compress(json.dumps(event).encode())
            sock.sendall(data + b'\x00')
        
        def recvLoop():
            eventsIn = EventsIn(sock)
            try:
                while True:
                    try:
                        event = eventsIn.send(None)
                    except (
                        ConnectionResetError, 
                        ConnectionAbortedError, 
                        StopIteration, 
                    ):
                        print('Connection closed by server')
                        break
                    if isinstance(event, str):
                        onUpdateUUID(event)
                    else:
                        onUpdateGamestate(Gamestate.fromPrimitive(event))
            finally:
                try:
                    eventsIn.send(True)
                except StopIteration:
                    pass
                else:
                    assert False
                onDisconnect()
        
        thread = Thread(target=recvLoop)
        yield write, thread, sock

class Root(tk.Tk):
    def __init__(self):
        super().__init__()
        self.gamestate = Gamestate.default()
        self.uuid: str | None = None
    
    @contextmanager
    def context(self, host: str, port: int):
        with NetworkClient(
            host, port,
            self.onUpdateGamestate, 
            self.onUpdateUUID, 
            self.onDisconnect,
        ) as (self.__write, receiveLoop, sock):
            receiveLoop.start()
            try:
                yield self
            finally:
                sock.close()
                receiveLoop.join()
    
    def submit(self, event: tp.Dict):
        event[EF.HASH] = hash(self.gamestate)
        self.__write(event)
    
    def setup(self):
        self.title("Web Set")
        self.bottomPanel = BottomPanel(self, self)
        self.refresh()
    
    def updateGamestateNow(self, gamestate: Gamestate):
        self.gamestate = gamestate
        ... # update GUI
    
    def onUpdateGamestate(self, gamestate: Gamestate):
        self.after_idle(self.updateGamestateNow, gamestate)
    
    def onUpdateUUID(self, uuid: str):
        self.uuid = uuid
        self.setup()
    
    def onDisconnect(self):
        def f():
            messagebox.showerror('Error: Server disconnected', 'Server disconneted!')
            self.quit()
        self.after_idle(f)
    
    def getMyself(self):
        return self.gamestate.seekPlayer(self.uuid)
    
    def refresh(self):
        self.bottomPanel.refresh()
        ...

class BottomPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.BOTTOM, fill=tk.X)

        col = 0

        self.buttonClearMyVote = ttk.Button(
            self, text='Clear My Vote', command=self.clearMyVote, 
        )
        self.buttonClearMyVote.grid(
            row=0, column=col, sticky=tk.EW, padx=PADX, pady=PADY, 
        )
        self.columnconfigure(col, weight=0)
        col += 1

        self.buttonCallSet = ttk.Button(
            self, text='Set!!!', command=self.callSet, 
        )
        self.buttonCallSet.grid(
            row=0, column=col, sticky=tk.EW, padx=PADX, pady=PADY, 
        )
        self.columnconfigure(col, weight=1)
        col += 1

        self.buttonVoteAccept = ttk.Button(
            self, text='Vote Accept', command=self.voteAccept, 
        )
        self.buttonVoteAccept.grid(
            row=0, column=col, sticky=tk.EW, padx=PADX, pady=PADY, 
        )
        self.columnconfigure(col, weight=0)
        col += 1

        self.buttonVoteUndo = ttk.Button(
            self, text='Vote Undo', command=self.voteUndo, 
        )
        self.buttonVoteUndo.grid(
            row=0, column=col, sticky=tk.EW, padx=PADX, pady=PADY, 
        )
        self.columnconfigure(col, weight=0)
        col += 1

    def clearMyVote(self):
        self.root.submit({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.IDLE })

    def callSet(self):
        if self.root.getMyself().shouted_set is None:
            self.root.submit({ EF.TYPE: ET.CALL_SET })
        else:
            self.root.submit({ EF.TYPE: ET.CANCEL_CALL_SET })
    
    def voteAccept(self):
        self.root.submit({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.ACCEPT })
    
    def voteUndo(self):
        self.root.submit({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.UNDO })
    
    def refresh(self):
        if self.root.getMyself().shouted_set is None:
            self.buttonCallSet.config(text='Set!!!')
        else:
            self.buttonCallSet.config(text='Just kidding...')

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    url = input('Server (ip_addr:port) > ')
    try:
        host, port_str = url.split(':')
    except ValueError:
        host = 'localhost'
        port_str = url
    port = int(port_str)
    root = Root()
    with root.context(host, port):
        root.mainloop()

if __name__ == "__main__":
    main()

import typing as tp
import os
import asyncio
from asyncio import StreamReader, StreamWriter
import threading

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from shared import *
from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

PADX = 5
PADY = 5

UpdateGamestateEvent = tp.Callable[[Gamestate], None]
UpdateUUIDEvent = tp.Callable[[str], None]
ArglessEvent = tp.Callable[[], None]
SubmitEventFunc = tp.Callable[[tp.Dict], None]

class Root(tk.Tk):
    def __init__(self, reader: StreamReader, writer: StreamWriter):
        super().__init__()
        self.reader = reader
        self.writer = writer
        self.gamestate = Gamestate.default()
        self.uuid: str | None = None
        self.lock = threading.Lock()
        self.setupBarrier = threading.Lock()
        self.setupBarrier.acquire()
    
    async def recvLoop(self):
        while True:
            try:
                event = await recvPrimitive(self.reader)
            except asyncio.IncompleteReadError:
                self.onUnexpectedDisconnect()
                break
            except asyncio.CancelledError:
                break
            if isinstance(event, str):
                self.onUpdateUUID(event)
            else:
                self.onUpdateGamestate(Gamestate.fromPrimitive(event))
    
    def send(self, event: tp.Dict):
        event[EF.HASH] = hash(self.gamestate)
        sendPrimitive(event, self.writer)
    
    def setup(self):
        self.setupBarrier.acquire()
        self.title("Web Set")
        self.bottomPanel = BottomPanel(self, self)
        self.refresh()
    
    def onUpdateGamestate(self, gamestate: Gamestate):
        with self.lock:
            self.gamestate = gamestate
            ... # update GUI
    
    def onUpdateUUID(self, uuid: str):
        self.uuid = uuid
        print('Initialization ok')
        self.setupBarrier.release()
    
    def onUnexpectedDisconnect(self):
        msg = 'Error: Unexpected disconnection by server.'
        print(msg)
        def f():
            messagebox.showerror(msg, msg)
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
        self.root.send({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.IDLE })

    def callSet(self):
        with self.root.lock:
            if self.root.getMyself().shouted_set is None:
                self.root.send({ EF.TYPE: ET.CALL_SET })
            else:
                self.root.send({ EF.TYPE: ET.CANCEL_CALL_SET })
    
    def voteAccept(self):
        self.root.send({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.ACCEPT })
    
    def voteUndo(self):
        self.root.send({ EF.TYPE: ET.VOTE, EF.VOTE: Vote.UNDO })
    
    def refresh(self):
        if self.root.getMyself().shouted_set is None:
            self.buttonCallSet.config(text='Set!!!')
        else:
            self.buttonCallSet.config(text='Just kidding...')

async def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    url = input('Server (ip_addr:port) > ')
    try:
        host, port_str = url.split(':')
    except ValueError:
        host = 'localhost'
        port_str = url
    port = int(port_str)
    print(f'Connecting to {host}:{port}... ', end='', flush=True)
    reader, writer = await asyncio.open_connection(host, port)
    print('ok')

    try:
        root: Root | None = None
        lock = asyncio.Lock()
        await lock.acquire()
        def runGUI():
            nonlocal root
            root = Root(reader, writer)
            lock.release()
            print('Waiting for initialization...')
            root.mainloop()

        taskTk = asyncio.create_task(asyncio.to_thread(runGUI))
        await lock.acquire()
        assert root is not None
        taskRecvLoop = asyncio.create_task(root.recvLoop())
        try:
            await taskTk
        except asyncio.CancelledError:
            pass
        finally:
            taskRecvLoop.cancel()
            await taskRecvLoop
    finally:
        print('closing... ', end='', flush=True)
        writer.close()
        await writer.wait_closed()
        print('ok')

if __name__ == "__main__":
    asyncio.run(main())

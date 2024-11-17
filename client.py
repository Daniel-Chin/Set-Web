import typing as tp
import os
import asyncio
from asyncio import StreamReader, StreamWriter
import threading
from contextlib import asynccontextmanager
import time

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from shared import *
from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

FPS = 30

PADX = 5
PADY = 5

@asynccontextmanager
async def Network():
    url = input('Server (ip_addr:port) > ')
    try:
        host, port_str = url.split(':')
    except ValueError:
        host = 'localhost'
        port_str = url
    port = int(port_str)
    print(f'Connecting to {host}:{port}...')
    reader, writer = await asyncio.open_connection(host, port)
    print('ok')
    try:
        yield reader, writer
    finally:
        print('closing...')
        writer.close()
        await writer.wait_closed()
        print('ok')

async def receiver(reader: StreamReader, queue: asyncio.Queue):
    try:
        while True:
            try:
                event = await recvPrimitive(reader)
            except asyncio.IncompleteReadError:
                break
            await queue.put(event)
        await queue.put(None)
    except asyncio.CancelledError:
        pass

class Root(tk.Tk):
    def __init__(
        self, queue: asyncio.Queue, writer: StreamWriter, 
        uuid: str, gamestate: Gamestate,
    ):
        super().__init__()
        self.queue = queue
        self.writer = writer
        self.uuid = uuid
        self.gamestate = gamestate
        self.lock = threading.Lock()
        self.is_closed = False

        self.setup()
    
    async def asyncMainloop(self):
        def onClose():
            self.is_closed = True
        self.protocol("WM_DELETE_WINDOW", onClose)
        while not self.is_closed:
            self.processQueue()
            self.update()
            next_update_time = time.time() + 1 / FPS
            self.processQueue()
            await asyncio.sleep(max(0, next_update_time - time.time()))
    
    def processQueue(self):
        while not self.queue.empty():
            event = self.queue.get_nowait()
            if event is None:
                self.onUnexpectedDisconnect()
                break
            self.onUpdateGamestate(Gamestate.fromPrimitive(event))
    
    def submit(self, event: tp.Dict):
        event[EF.HASH] = self.gamestate.mutableHash()
        sendPrimitive(event, self.writer)
    
    def setup(self):
        self.title("Web Set")
        self.bottomPanel = BottomPanel(self, self)
        self.refresh()
    
    def onUpdateGamestate(self, gamestate: Gamestate):
        with self.lock:
            self.gamestate = gamestate
            ... # update GUI
    
    def onUnexpectedDisconnect(self):
        msg = 'Error: Unexpected disconnection by server.'
        print(msg)
        def f():
            messagebox.showerror(msg, msg)
            self.is_closed = True
        self.after_idle(f)
    
    def getMyself(self):
        return self.gamestate.seekPlayer(self.uuid)
    
    def refresh(self):
        self.bottomPanel.refresh()
        ...

class BottomPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
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
        with self.root.lock:
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

async def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    async with Network() as (reader, writer):
        print('Waiting for player ID assignment...')
        uuid = await recvPrimitive(reader)
        print('ok')
        print('Waiting for gamestate...')
        gamestate = Gamestate.fromPrimitive(await recvPrimitive(reader))
        print('ok')
        queue = asyncio.Queue()
        receiveTask = asyncio.create_task(receiver(reader, queue))

        root = Root(queue, writer, uuid, gamestate)
        
        try:
            await root.asyncMainloop()
        except asyncio.CancelledError:
            pass
        finally:
            receiveTask.cancel()
            await receiveTask

if __name__ == "__main__":
    asyncio.run(main())

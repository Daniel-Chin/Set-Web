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
from shared import (
    ServerEventType as SET, ServerEventField as SEF,
    ClientEventType as CET, ClientEventField as CEF, 
)
from gamestate import *

FPS = 30

PADX = 16
PADY = 16

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
            type_ = SET(event[SEF.TYPE])
            if type_ == SET.GAMESTATE:
                self.onUpdateGamestate(Gamestate.fromPrimitive(event[SEF.CONTENT]))
            elif type_ == SET.YOU_ARE:
                assert False
            elif type_ == SET.POPUP_MESSAGE:
                title, msg = event[SEF.CONTENT]
                print('>>>>>> Message from server')
                print(title)
                print(msg)
                print('<<<<<<')
                def f():
                    messagebox.showinfo(title, msg)
                self.after_idle(f)
            else:
                raise ValueError(f'Unexpected event type: {type_}')
    
    def submit(self, event: tp.Dict):
        event[CEF.HASH] = self.gamestate.mutableHash()
        co = sendPrimitive(event, self.writer)
        asyncio.create_task(co)
    
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

        self.buttonClearMyVote = ttk.Button(
            self, text='Clear My Vote', command=self.clearMyVote, 
        )
        self.buttonClearMyVote.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        self.buttonCallSet = ttk.Button(
            self, text='Set!!!', command=self.callSet, 
        )
        self.buttonCallSet.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
            expand=True, fill=tk.X,
        )

        self.buttonVoteAccept = ttk.Button(
            self, text='Vote Accept', command=self.voteAccept, 
        )
        self.buttonVoteAccept.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        self.buttonVoteUndo = ttk.Button(
            self, text='Vote Undo', command=self.voteUndo, 
        )
        self.buttonVoteUndo.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

    def clearMyVote(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.IDLE })

    def callSet(self):
        with self.root.lock:
            if self.root.getMyself().shouted_set is None:
                self.root.submit({ CEF.TYPE: CET.CALL_SET })
            else:
                self.root.submit({ CEF.TYPE: CET.CANCEL_CALL_SET })
    
    def voteAccept(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.ACCEPT })
    
    def voteUndo(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.UNDO })
    
    def refresh(self):
        if self.root.getMyself().shouted_set is None:
            self.buttonCallSet.config(text='Set!!!')
        else:
            self.buttonCallSet.config(text='Just kidding...')

async def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    async with Network() as (reader, writer):
        print('Waiting for player ID assignment...')
        event = await recvPrimitive(reader)
        assert SET(event[SEF.TYPE]) == SET.YOU_ARE
        uuid = event[SEF.CONTENT]
        print('ok')
        print('Waiting for gamestate...')
        event = await recvPrimitive(reader)
        assert SET(event[SEF.TYPE]) == SET.GAMESTATE
        gamestate = Gamestate.fromPrimitive(event[SEF.CONTENT])
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

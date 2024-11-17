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
from tkinter import simpledialog
from uuid import uuid4

from shared import *
from shared import (
    ServerEventType as SET, ServerEventField as SEF,
    ClientEventType as CET, ClientEventField as CEF, 
)
from env_wrap import *
from gamestate import *
from texture import Texture

ALLOW_ACCEPT_AFTER_CHANGE = 1 # sec
HEAT_LASTS_FOR = 3 # sec

FPS = 30

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
        self.last_info_change = 0

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
        self.texture = Texture(self)
        self.title("Web Set")
        style = ttk.Style()
        style.theme_use("clam")
        self.bottomPanel = BottomPanel(self, self)
        upperBody = ttk.Frame(self)
        upperBody.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.leftPanel = LeftPanel(self, upperBody)
        self.refresh()
    
    def onUpdateGamestate(self, gamestate: Gamestate):
        with self.lock:
            if not self.gamestate.isCardSelectionEqual(gamestate):
                self.last_info_change = time.time()
            self.gamestate = gamestate
            self.refresh()
    
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
        self.leftPanel.refresh()
        ...

class BottomPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.BOTTOM, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

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
        if self.buttonVoteAccept['state'] == tk.DISABLED:
            return
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.ACCEPT })
    
    def voteUndo(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.UNDO })
    
    def refresh(self):
        if self.root.getMyself().shouted_set is None:
            self.buttonCallSet.config(text='Set!!!')
        else:
            self.buttonCallSet.config(text='Just kidding...')
        disableIf(self.buttonClearMyVote, (
            self.root.getMyself().voting == Vote.IDLE
        ))
        disableIf(self.buttonVoteUndo, (
            self.root.getMyself().voting == Vote.UNDO
        ))
    
    def update(self):
        disableIf(self.buttonVoteAccept, (
            time.time() - self.root.last_info_change < ALLOW_ACCEPT_AFTER_CHANGE
        ) or self.root.getMyself().voting == Vote.ACCEPT)
        super().update()

class LeftPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.selfConfigBar = SelfConfigBar(root, self)
    
    def refresh(self):
        ...

class SelfConfigBar(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        buttonChangeMyName = ttk.Button(
            self, text='Change My Name', command=self.changeMyName, 
        )
        buttonChangeMyName.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        buttonChangeMyColor = ttk.Button(
            self, text='Change My Color', command=self.changeMyColor, 
        )
        buttonChangeMyColor.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )
    
    def changeMyName(self):
        old_name = self.root.getMyself().name
        new_name = simpledialog.askstring(
            'Change My Name', 'Enter new name', initialvalue=old_name, 
        )
        if new_name is None:
            return
        self.root.submit({ CEF.TYPE: CET.CHANGE_NAME, CEF.TARGET_VALUE: new_name })
    
    def changeMyColor(self):
        old_color = self.root.getMyself().color
        new_color = simpledialog.askstring(
            'Change My Color', 
            'Enter new color "r,g,b", 0 <= each <= 255. Hint: use a dark color for better contrast.', 
            initialvalue=old_color, 
        )
        if new_color is None:
            return
        self.root.submit({ CEF.TYPE: CET.CHANGE_COLOR, CEF.TARGET_VALUE: new_color })

class PlayerStripe(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk, uuid: str):
        super().__init__(parent)
        self.root = root
        self.uuid = uuid
        self.pack(side=tk.TOP, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.col_0 = ttk.Frame(self)
        self.col_0.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.col_1 = ttk.Frame(self)
        self.col_1.pack(side=tk.LEFT, fill=tk.BOTH)
        self.col_2 = ttk.Frame(self)
        self.col_2.pack(side=tk.LEFT, fill=tk.BOTH)
        
        self.labelName = ttk.Label(self.col_0, text='<name>')
        self.labelName.pack(side=tk.TOP, padx=PADX, pady=PADY)

        self.labelShoutSet = ttk.Label(self.col_0, text='<shout_set>')
        self.labelShoutSet.pack(side=tk.TOP, padx=PADX, pady=PADY)

        self.labelVoting = ttk.Label(self.col_0, text='<voting>')
        self.labelVoting.pack(side=tk.TOP, padx=PADX, pady=PADY)

        ...

    def getPlayer(self):
        return self.root.gamestate.seekPlayer(self.uuid)
    
    def refresh(self):
        ...

class DisplayCase(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.row_0 = ttk.Frame(self)
        self.row_0.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.row_1 = ttk.Frame(self)
        self.row_1.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        ...

class SmartCardWidget(ttk.Frame):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        is_public_not_display_case: bool, 
        coord: tp.Tuple[int, int] | int,
        smartCard: SmartCard | None,
    ):
        self.unique_style_name = str(uuid4()) + '.TFrame'
        super().__init__(parent, style=self.unique_style_name)
        self.root = root
        self.is_public_not_display_case = is_public_not_display_case
        self.coord = coord
        self.smartCard = smartCard

        self.checksBar = ttk.Frame(self)
        self.checksBar.pack(side=tk.TOP, pady=(PADY, 0))
        self.checkLabels: tp.List[ttk.Label] = []
    
        if is_public_not_display_case:
            card_width  = CARD_WIDTH
            card_height = CARD_HEIGHT
        else:
            card_width  = SMALL_CARD_WIDTH
            card_height = SMALL_CARD_HEIGHT
        self.canvas = tk.Canvas(self, width=card_width, height=card_height)
        self.canvas.pack(side=tk.TOP, padx=PADX, pady=(0, PADY))
        self.canvas.bind('<Button-1>', self.onClick)

        self.setHeat(0)
        self.last_drew_card = smartCard and smartCard.card
        self.refresh(smartCard)

    def refresh(self, smartCard: SmartCard | None):
        for label in self.checkLabels:
            label.destroy()
        if smartCard is not None:
            for uuid in smartCard.selected_by:
                player = self.root.gamestate.seekPlayer(uuid)
                hx = rgbToHex(*[int(x) for x in player.color.split(',')])
                label = ttk.Label(
                    self.checksBar, text='X', background=hx, 
                    foreground='white', 
                )
                label.pack(side=tk.LEFT, padx=3)
                self.checkLabels.append(label)

        card = smartCard and smartCard.card
        if self.last_drew_card != card:
            self.canvas.delete('all')
            if card is not None:
                self.canvas.create_image(
                    0, 0, anchor=tk.NW, 
                    image=self.root.texture.get(*card), 
                )
    
    def update(self):
        if self.smartCard is not None:
            heat = 1.0 - (time.time() - self.smartCard.birth) / HEAT_LASTS_FOR
            self.setHeat(heat)
        super().update()

    def setHeat(self, heat: float):
        heat = min(1.0, max(0.0, heat))
        luminosity = round((1 - heat) * 255)
        style = ttk.Style()
        style.configure(self.unique_style_name, background=rgbToHex(
            luminosity, luminosity, luminosity, 
        ))
    
    def onClick(self, _):
        if self.is_public_not_display_case:
            type_ = CET.TOGGLE_SELECT_CARD_PUBLIC
        else:
            type_ = CET.TOGGLE_SELECT_CARD_DISPLAY
        ...

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

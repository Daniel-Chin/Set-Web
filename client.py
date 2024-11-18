import os
import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
from contextlib import asynccontextmanager
import time
from abc import ABC, abstractmethod
import math
import gzip

import tkinter as tk
from tkinter import ttk, font
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

BOLD_STYLE = 'Bold.TLabel'
SMALL_STYLE = 'small.TLabel'

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
        self.title('Web Set')
        style = ttk.Style()
        style.theme_use('clam')
        padding = (
            round(FONT_SIZE * 0.5), round(FONT_SIZE * 0.1), 
        )
        for style_name in (
            'TLabel', 'TButton', 'TSpinbox',
        ):
            style.configure(
                style_name, 
                padding=padding,
                font=(FONT, FONT_SIZE),
            )
        defaultFont = font.nametofont("TkDefaultFont")
        defaultFont.configure(size=FONT_SIZE)
        self.option_add("*TSpinbox.Font", defaultFont)  # style.configure doesn't work for Spinbox
        style.configure('TSpinbox', arrowsize=FONT_SIZE)
        style.configure(
            BOLD_STYLE, font=(FONT, FONT_SIZE, font.BOLD), 
            padding=padding, 
        )
        style.configure(
            SMALL_STYLE, font=(FONT, FONT_SIZE // 3), 
            padding=(0, 0), 
        )

        self.bottomPanel = BottomPanel(self, self)
        upperBody = ttk.Frame(self)
        upperBody.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.leftPanel = LeftPanel(self, upperBody)
        rightBody = ttk.Frame(upperBody)
        rightBody.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.publicZoneTopPanel = PublicZoneTopPanel(self, rightBody)
        self.publicZone = PublicZone(self, rightBody)
        self.refresh()
        def freezeSize():
            self.geometry(f'{self.winfo_width()}x{self.winfo_height()}')
        self.after(100, freezeSize)
    
    def onUpdateGamestate(self, gamestate: Gamestate):
        if not self.gamestate.isCardSelectionEqual(gamestate):
            self.last_info_change = time.time()
        self.gamestate = gamestate
        self.refresh()
        with open(f'./logs/{self.uuid}.txt', 'w') as f:
            self.gamestate.printDebug(file=f)
    
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
        self.publicZoneTopPanel.refresh()
        self.publicZone.refresh()

    def getPlayer(self, player_i: int):
        return self.gamestate.players[player_i]
    
    def newButton(
        self, parent: tk.Widget | tk.Tk, text: str, 
        command: tp.Callable, special_shortcut: str | None = None,
    ):
        if special_shortcut is not None:
            key = special_shortcut
            underline = -1
        elif '_' in text:
            left, right = text.split('_')
            text = left + right
            key = 'Alt-' + right[0].lower()
            underline = len(left)
        else:
            key = None
            underline = -1
        button = ttk.Button(parent, text=text, command=command, underline=underline)
        if key is not None:
            self.bind(f'<{key}>', lambda _: button.invoke(), add=True)
        return button

class BottomPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.BOTTOM, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.buttonClearMyVote = root.newButton(
            self, text='Clear My Vote (Esc)', command=self.clearMyVote, 
            special_shortcut='Escape', 
        )
        self.buttonClearMyVote.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        self.buttonCallSet = root.newButton(
            self, text='_Set!!!', command=self.callSet, 
        )
        self.buttonCallSet.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
            expand=True, fill=tk.X,
        )

        self.buttonVoteAccept = root.newButton(
            self, text='Vote _Accept', command=self.voteAccept, 
        )
        self.buttonVoteAccept.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        self.buttonVoteUndo = root.newButton(
            self, text='Vote _Undo', command=self.voteUndo, 
        )
        self.buttonVoteUndo.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        self.root.after(1000 // FPS, self.animate)

    def clearMyVote(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.IDLE })

    def callSet(self):
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
            self.buttonCallSet.config(text='Set!!!', underline=0)
        else:
            self.buttonCallSet.config(text='Just kidding...', underline=2)
        disableIf(self.buttonClearMyVote, (
            self.root.getMyself().voting == Vote.IDLE
        ))
        disableIf(self.buttonVoteUndo, (
            self.root.getMyself().voting == Vote.UNDO
        ))
    
    def animate(self):
        disableIf(self.buttonVoteAccept, (
            time.time() - self.root.last_info_change < ALLOW_ACCEPT_AFTER_CHANGE
        ) or self.root.getMyself().voting == Vote.ACCEPT)
        self.root.after(1000 // FPS, self.animate)

class LeftPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.selfConfigBar = SelfConfigBar(root, self)
        self.playerStripes: tp.List[PlayerStripe] = []
        self.deckArea = DeckArea(root, self)
    
    def refresh(self):
        if len(self.playerStripes) != len(self.root.gamestate.players):
            for stripe in self.playerStripes:
                stripe.destroy()
            self.playerStripes = [
                PlayerStripe(self.root, self, i)
                for i in range(len(self.root.gamestate.players))
            ]
        for playerStripe in self.playerStripes:
            playerStripe.refresh()
        self.deckArea.refresh()

class SelfConfigBar(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        buttonChangeMyName = root.newButton(
            self, text='Change My Name', command=self.changeMyName, 
        )
        buttonChangeMyName.pack(
            side=tk.LEFT, padx=PADX, pady=PADY, 
        )

        buttonChangeMyColor = root.newButton(
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
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        player_i: int, 
    ):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)
        self.player_i = player_i

        self.col_0 = ttk.Frame(self)
        self.col_0.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.col_1 = ttk.Frame(self)
        self.col_1.pack(side=tk.LEFT, fill=tk.BOTH)
        self.col_2 = ttk.Frame(self)
        self.col_2.pack(side=tk.LEFT, fill=tk.BOTH)
        
        self.labelName = ttk.Label(
            self.col_0, text='<name>', 
            anchor=tk.W,
            foreground='white', background='black',
        )
        self.labelName.pack(
            side=tk.TOP, fill=tk.X, padx=PADX, pady=(PADY, 0), 
            expand=True,
        )

        self.labelShoutSet = ttk.Label(
            self.col_0, text='<shout_set>', 
            foreground='white', 
            anchor=tk.W,
        )
        self.labelShoutSet.pack(
            side=tk.TOP, fill=tk.X, padx=PADX, pady=(0, 0), 
            expand=True,
        )

        self.labelVoting = ttk.Label(
            self.col_0, text='<voting>', 
            anchor=tk.W,
        )
        self.labelVoting.pack(
            side=tk.TOP, fill=tk.X, padx=PADX, pady=(0, PADY), 
            expand=True,
        )

        self.displayCase = DisplayCase(root, self.col_1, player_i)

        self.thicknessIndicator = ThicknessIndicator(
            self.col_2, THICKNESS_INDICATOR_WEALTH, 
        )
        self.thicknessIndicator.pack(side=tk.TOP, padx=PADX, pady=(0, 0))

        ttk.Label(self.col_2, text='Wins:', anchor=tk.W).pack(
            side=tk.TOP, fill=tk.X, padx=PADX, pady=(0, 0),
        )
        
        self.winCounter = WinCounter(root, self.col_2, player_i)
        self.winCounter.pack(side=tk.TOP, padx=PADX, pady=(0, PADY))
    
    def refresh(self):
        player = self.root.getPlayer(self.player_i)
        
        self.labelName.config(text=player.name)
        self.labelName.config(background=rgbStrToHex(player.color))
        self.labelShoutSet.config(
            text=(
                f'Set! {player.shouted_set:.2f} sec' 
                if player.shouted_set is not None else 
                ' ' * 35
            ), 
            background=(
                'black' if player.shouted_set is not None else 'white'
            ),
        )
        self.labelVoting.config(text=(
            '' if player.voting == Vote.IDLE else f'Voting: {player.voting.name}'
        ))

        self.displayCase.refresh(player)

        self.thicknessIndicator.refresh(player.wealth_thickness)
        self.winCounter.refresh(player.n_of_wins)

class DisplayCase(ttk.Frame):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        player_i: int,
    ):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.config(borderwidth=1, relief=tk.SOLID)
        self.player_i = player_i

        self.smartCardWidgets = [
            SmartCardWidget(root, self, False, (player_i, i), None)
            for i in range(4)
        ]
        [x.pack(
            side=tk.LEFT, fill=tk.Y,
        ) for x in self.smartCardWidgets]
    
    def refresh(self, player: Player):
        for widget, smartCard in zip(self.smartCardWidgets, player.display_case):
            widget.refresh(smartCard)

class SmartCardWidget(ttk.Frame):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        is_public_not_display_case: bool, 
        coord: tp.Tuple[int, int],
        smartCard: SmartCard | None,
    ):
        self.unique_style_name = str(uuid4()) + '.TFrame'
        super().__init__(parent, style=self.unique_style_name)
        self.root = root
        self.is_public_not_display_case = is_public_not_display_case
        self.coord = coord
        self.smartCard = smartCard

        if is_public_not_display_case:
            card_width  = CARD_WIDTH
            card_height = CARD_HEIGHT
            padx = PADX
            pady = PADY
        else:
            card_width  = round(SMALL_CARD_RATIO * CARD_WIDTH)
            card_height = round(SMALL_CARD_RATIO * CARD_HEIGHT)
            padx = round(SMALL_CARD_RATIO * PADX)
            pady = round(SMALL_CARD_RATIO * PADY)

        self.checksBar = ttk.Frame(self, style=self.unique_style_name)
        self.checksBar.pack(side=tk.TOP, pady=(pady, 0))
        self.newSelectionLabel('', 'white')
        self.checkLabels: tp.List[ttk.Label] = []
    
        self.canvas = tk.Canvas(self, width=card_width, height=card_height)
        self.canvas.pack(side=tk.TOP, padx=padx, pady=(0, pady))
        self.canvas.bind('<Button-1>', self.onClick)

        self.setHeat(0)
        self.last_rendered_card = None

        self.root.after(1000 // FPS, self.animate)

    def newSelectionLabel(self, text: str, background: str):
        label = ttk.Label(
            self.checksBar, text=text, background=background, 
            foreground='white', 
            style=SMALL_STYLE,
        )
        padx = 3
        # if not self.is_public_not_display_case:
        #     padx = round(SMALL_CARD_RATIO * padx)
        label.pack(side=tk.LEFT, padx=padx)
        return label
    
    def refresh(self, smartCard: SmartCard | None):
        self.smartCard = smartCard
        for label in self.checkLabels:
            label.destroy()
        self.checkLabels.clear()
        if smartCard is not None:
            for uuid in smartCard.selected_by:
                player = self.root.gamestate.seekPlayer(uuid)
                hx = rgbStrToHex(player.color)
                label = self.newSelectionLabel('X', hx)
                self.checkLabels.append(label)

        card = smartCard and smartCard.card
        if self.last_rendered_card != card:
            self.last_rendered_card = card
            self.canvas.delete('all')
            if card is not None:
                self.canvas.create_image(
                    0, 0, anchor=tk.NW, 
                    image=self.root.texture.get(
                        *card, not self.is_public_not_display_case, 
                    ), 
                )
    
    def animate(self):
        if not self.winfo_exists():
            return
        if self.smartCard is not None:
            heat = 1.0 - (time.time() - self.smartCard.birth) / HEAT_LASTS_FOR
            self.setHeat(heat)
        self.root.after(1000 // FPS, self.animate)

    def setHeat(self, heat: float):
        heat = min(1.0, max(0.0, heat))
        luminosity = round((1 - heat) * 255)
        style = ttk.Style()
        style.configure(self.unique_style_name, background=rgbToHex(
            luminosity, luminosity, luminosity, 
        ))
    
    def onClick(self, _):
        if self.is_public_not_display_case:
            self.root.submit({ 
                CEF.TYPE: CET.TOGGLE_SELECT_CARD_PUBLIC, 
                CEF.TARGET_VALUE: self.coord, 
            })
        else:
            player_i, card_i = self.coord
            self.root.submit({ 
                CEF.TYPE: CET.TOGGLE_SELECT_CARD_DISPLAY, 
                CEF.TARGET_PLAYER: self.root.gamestate.players[player_i].uuid, 
                CEF.TARGET_VALUE: card_i, 
            })

class ThicknessIndicator(tk.Canvas):
    def __init__(
        self, parent: tk.Widget | tk.Tk, 
        size_: tp.Tuple[int, int], 
    ):
        super().__init__(
            parent, 
            width=size_[0], height=size_[1], 
        )
        self.size_ = size_
        self.last_thickness = 0
    
    def refresh(self, n_cards: int):
        if self.last_thickness == n_cards:
            return
        self.last_thickness = n_cards
        self.delete('all')
        # width = max(10, self.winfo_width())
        for i in range(0, math.ceil(n_cards / THICKNESS_INDICATOR_CARD_PER_LINE)):
            y = self.size_[1] - i * THICKNESS_INDICATOR_CARD_INTERVAL
            self.create_line(
                0, y, self.size_[0], y, 
                fill='black', 
                width=THICKNESS_INDICATOR_CARD_THICKNESS, 
            )

class DeltaSpinbox(ttk.Spinbox, ABC):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        from_: int, 
    ):
        super().__init__(
            parent, from_=from_, to=999, state='readonly',
            width=0, 
            command=self.onClick,
        )
        self.root = root
        self.last_value: int | None = None
    
    def onClick(self):
        if self.last_value is None:
            return
        delta = int(self.get()) - self.last_value
        self.last_value += delta
        self.submitDelta(delta)
    
    @abstractmethod
    def submitDelta(self, delta: int):
        raise NotImplementedError()
    
    def refresh(self, value: int):
        if self.last_value != value:
            self.set(value)
            self.last_value = value

class WinCounter(DeltaSpinbox):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        player_i: int,
    ):
        super().__init__(root, parent, 0)
        self.player_i = player_i

    def submitDelta(self, delta: int):
        self.root.submit({ 
            CEF.TYPE: CET.ACC_N_WINS, 
            CEF.TARGET_PLAYER: self.root.getPlayer(self.player_i).uuid, 
            CEF.TARGET_VALUE: delta, 
        })

class DeckArea(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.BOTTOM, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.thicknessIndicator = ThicknessIndicator(
            self, THICKNESS_INDICATOR_DECK, 
        )
        self.thicknessIndicator.grid(
            column=0, row=0, rowspan=2, 
            padx=PADX, pady=PADY, 
        )

        self.buttonDealCard = root.newButton(
            self, text='_Deal 1 Card', command=self.dealCard, 
        )
        self.buttonDealCard.grid(
            column=1, row=0, rowspan=2, 
            padx=0, pady=PADY, sticky=tk.NSEW,
        )
        self.columnconfigure(1, weight=1)

        self.buttonCountCards = root.newButton(
            self, text='Count Cards', command=self.countCards,
        )
        self.buttonCountCards.grid(
            column=2, row=0,
            padx=PADX, pady=(PADY, 0), sticky=tk.NSEW,
        )

        self.buttonNewGame = root.newButton(
            self, text='New Game', command=self.newGame,
        )
        self.buttonNewGame.grid(
            column=2, row=1,
            padx=PADX, pady=PADY, sticky=tk.NSEW,
        )
    
    def dealCard(self):
        self.root.submit({ CEF.TYPE: CET.DEAL_CARD })
    
    def countCards(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.COUNT_CARDS })
    
    def newGame(self):
        self.root.submit({ CEF.TYPE: CET.VOTE, CEF.VOTE: Vote.NEW_GAME })
    
    def refresh(self):
        self.thicknessIndicator.refresh(self.root.gamestate.nCardsInDeck())
        disableIf(self.buttonCountCards, (
            self.root.getMyself().voting == Vote.COUNT_CARDS
        ))
        disableIf(self.buttonNewGame, (
            self.root.getMyself().voting == Vote.NEW_GAME
        ))

class PublicZoneTopPanel(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.X)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.buttonClearSelection = root.newButton(
            self, text='Clear Select (Esc)', command=self.clearSelection, 
            special_shortcut='Escape',
        )
        self.buttonClearSelection.pack(side=tk.RIGHT, padx=PADX, pady=PADY)

        self.colSizer = PublicZoneSizer(root, self, 1)
        self.colSizer.pack(side=tk.RIGHT, padx=(0, PADX), pady=PADY)
        ttk.Label(
            self, text='# cols:', 
        ).pack(side=tk.RIGHT, padx=0, pady=PADY)

        self.rowSizer = PublicZoneSizer(root, self, 0)
        self.rowSizer.pack(side=tk.RIGHT, padx=(0, PADX), pady=PADY)
        ttk.Label(
            self, text='# rows:', 
        ).pack(side=tk.RIGHT, padx=0, pady=PADY)
    
    def clearSelection(self):
        self.root.submit({ CEF.TYPE: CET.CLEAR_MY_SELECTIONS })
    
    def refresh(self):
        zone = self.root.gamestate.public_zone
        self.rowSizer.refresh(len(zone))
        self.colSizer.refresh(len(zone[0]))
        nothing_selected = True
        for smartCard in self.root.gamestate.AllSmartCards():
            if self.root.getMyself().uuid in smartCard.selected_by:
                nothing_selected = False
                break
        disableIf(self.buttonClearSelection, nothing_selected)

class PublicZoneSizer(DeltaSpinbox):
    def __init__(
        self, root: Root, parent: tk.Widget | tk.Tk, 
        axis: int, 
    ):
        super().__init__(root, parent, 1)
        self.axis = axis

    def submitDelta(self, delta: int):
        acc = [0, 0]
        acc[self.axis] = delta
        self.root.submit({
            CEF.TYPE: CET.ACC_PUBLIC_ZONE_SHAPE, 
            CEF.TARGET_VALUE: tuple(acc), 
        })

class PublicZone(ttk.Frame):
    def __init__(self, root: Root, parent: tk.Widget | tk.Tk):
        super().__init__(parent)
        self.root = root
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.config(borderwidth=1, relief=tk.SOLID)

        self.smartCardWidgets: tp.List[tp.List[SmartCardWidget]] = [[]]
    
    def refresh(self):
        old_n_rows = len(self.smartCardWidgets)
        old_n_cols = len(self.smartCardWidgets[0])
        zone = self.root.gamestate.public_zone
        new_n_rows = len(zone)
        new_n_cols = len(zone[0])
        if old_n_rows != new_n_rows or old_n_cols != new_n_cols:
            for row in self.smartCardWidgets:
                for widget in row:
                    widget.destroy()
            self.smartCardWidgets = [
                [SmartCardWidget(
                    self.root, self, True, (y, x), 
                    zone[y][x], 
                ) for x in range(new_n_cols)]
                for y in range(new_n_rows)
            ]
            for y, row in enumerate(self.smartCardWidgets):
                for x, widget in enumerate(row):
                    widget.grid(
                        row=y, column=x, sticky=tk.NSEW, 
                        padx=PADX, pady=PADY,
                    )
        for y, row in enumerate(self.smartCardWidgets):
            for x, widget in enumerate(row):
                widget.refresh(zone[y][x])

async def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for filename in os.listdir('./logs'):
        if filename.endswith('.txt'):
            os.remove(f'./logs/{filename}')
    async with Network() as (reader, writer):
        print('Waiting for player ID assignment...')
        event = await recvPrimitive(reader)
        assert SET(event[SEF.TYPE]) == SET.YOU_ARE
        uuid = event[SEF.CONTENT]
        print('ok')
        print('My player ID:', uuid)
        print('Waiting for texture...')
        texture_data = gzip.decompress(await recvStream(reader))
        print('ok')
        with open(PNG, 'wb') as f:
            f.write(texture_data)
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

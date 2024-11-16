from __future__ import annotations

import typing as tp
from dataclasses import dataclass, asdict
from enum import Enum

from uuid import UUID

from shared import *

class Vote(Enum):
    IDLE = 'IDLE'
    NEW_GAME = 'NEW_GAME'
    ACCEPT = 'ACCEPT'

@dataclass
class Player:
    uuid: UUID
    name: str
    color: str
    voting: Vote = Vote.IDLE
    shouted_set: tp.Optional[float] = None  # timestamp
    wealth_thickness: int = 0
    n_of_wins: int = 0
    display_case: tp.List[SmartCard] = []
    display_case_hidden: bool = False

@dataclass
class SmartCard:
    card: Card
    selected_by: tp.List[UUID] = []
    birth: float

    def toPrimitive(self):
        d = asdict(self)
        s = ''
        s += str(self.card[0] + self.card[1] * 3)
        s += str(self.card[2] + self.card[3] * 3)
        d['card'] = s
        return d
    
    @classmethod
    def fromPrimitive(cls, d):
        s = d['card']
        card = (int(s[0]) % 3, int(s[0]) // 3, int(s[1]) % 3, int(s[1]) // 3)
        return cls(
            card=card, 
            selected_by=d['selected_by'], 
            birth=d['birth'], 
        )

@dataclass
class Gamestate:
    cards_in_deck: tp.Dict[tp.Tuple[int, int, int, int], bool] = {}
    players: tp.List[Player] = []
    public_zone: tp.List[SmartCard] = []
    public_zone_n_cols: int = 4
    public_zone_n_rows: int = 3

    def validate(self):
        n_set = 0
        for player in self.players:
            if player.shouted_set is not None:
                n_set += 1
        if n_set != 1:
            for player in self.players:
                if player.voting == Vote.ACCEPT:
                    player.voting = Vote.IDLE

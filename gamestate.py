from __future__ import annotations

import typing as tp
from dataclasses import dataclass, asdict
from enum import Enum

from uuid import UUID

from shared import *

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

    def toPrimitive(self):
        d = asdict(self)
        d['display_case'] = [card.toPrimitive() for card in self.display_case]
        return d
    
    @classmethod
    def fromPrimitive(cls, d: dict):
        return cls(
            uuid=d['uuid'], 
            name=d['name'], 
            color=d['color'], 
            voting=Vote(d['voting']), 
            shouted_set=d['shouted_set'], 
            wealth_thickness=d['wealth_thickness'], 
            n_of_wins=d['n_of_wins'], 
            display_case=[SmartCard.fromPrimitive(card) for card in d['display_case']], 
            display_case_hidden=d['display_case_hidden'], 
        )

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
    def fromPrimitive(cls, d: dict):
        s = d['card']
        card = (int(s[0]) % 3, int(s[0]) // 3, int(s[1]) % 3, int(s[1]) // 3)
        return cls(
            card=card, 
            selected_by=d['selected_by'], 
            birth=d['birth'], 
        )

@dataclass
class Gamestate:
    cards_in_deck: tp.Dict[tp.Tuple[int, int, int, int], bool]
    players: tp.List[Player]
    public_zone: tp.List[tp.List[SmartCard]]
    public_zone_n_rows: int
    public_zone_n_cols: int

    @classmethod
    def default(cls):
        n_rows = 3
        n_cols = 4
        return cls(
            cards_in_deck=dict.fromkeys(iterAllCards(), True), 
            players=[], 
            public_zone=[[] for _ in range(n_rows)], 
            public_zone_n_rows=n_rows, 
            public_zone_n_cols=n_cols, 
        )

    def validate(self):
        n_set = 0
        for player in self.players:
            if player.shouted_set is not None:
                n_set += 1
        if n_set != 1:
            for player in self.players:
                if player.voting == Vote.ACCEPT:
                    player.voting = Vote.IDLE
    
    def toPrimitive(self):
        d = asdict(self)
        def bools():
            for idx in iterAllCards():
                yield self.cards_in_deck[idx]
        d['cards_in_deck'] = boolsToBytes(bools())
        d['players'] = [player.toPrimitive() for player in self.players]
        d['public_zone'] = [[
            card.toPrimitive() for card in row
        ] for row in self.public_zone]
        return d
    
    @classmethod
    def fromPrimitive(cls, d: dict):
        cards_in_deck: tp.Dict[tp.Tuple[int, int, int, int], bool] = {}
        for idx, bool_ in zip(iterAllCards(), bytesToBools(d['cards_in_deck'])):
            cards_in_deck[idx] = bool_
        return cls(
            cards_in_deck=cards_in_deck, 
            players=[Player.fromPrimitive(player) for player in d['players']], 
            public_zone=[[
                SmartCard.fromPrimitive(card) for card in row
            ] for row in d['public_zone']],
            public_zone_n_cols=d['public_zone_n_cols'], 
            public_zone_n_rows=d['public_zone_n_rows'], 
        )
    
    def seekPlayer(self, uuid: UUID):
        for player in self.players:
            if player.uuid == uuid:
                return player
        raise KeyError(f'{uuid} not present')

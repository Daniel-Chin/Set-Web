from __future__ import annotations

import typing as tp
from dataclasses import dataclass, asdict, field

from shared import *

@dataclass()
class Player:
    uuid: str
    name: str
    color: str
    voting: Vote = Vote.IDLE
    shouted_set: tp.Optional[float] = None  # timestamp
    wealth_thickness: int = 0
    n_of_wins: int = 0
    display_case: tp.List[SmartCard] = field(default_factory=list)
    display_case_hidden: bool = False

    def mutableHash(self):
        return hash((
            self.uuid, self.name, self.color, self.voting.value, 
            self.shouted_set, self.wealth_thickness, self.n_of_wins, 
            tuple([card.mutableHash() for card in self.display_case]), 
            self.display_case_hidden, 
        ))

    def toPrimitive(self):
        d = asdict(self)
        d['display_case'] = [card.toPrimitive() for card in self.display_case]
        d['voting'] = self.voting.value
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

@dataclass()
class SmartCard:
    card: Card
    birth: float
    selected_by: tp.List[str] = field(default_factory=list)

    def mutableHash(self):
        return hash((
            self.card, self.birth, tuple(self.selected_by),
        ))

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
            birth=d['birth'], 
            selected_by=d['selected_by'], 
        )

@dataclass()
class Gamestate:
    cards_in_deck: tp.Dict[tp.Tuple[int, int, int, int], bool]
    players: tp.List[Player]
    public_zone: tp.List[tp.List[SmartCard | None]]

    def mutableHash(self):
        return hash((
            tuple([self.cards_in_deck[i] for i in iterAllCards()]), 
            tuple([player.mutableHash() for player in self.players]), 
            tuple([tuple([sC and sC.mutableHash() for sC in row]) for row in self.public_zone]),
        ))

    @classmethod
    def default(cls):
        return cls(
            cards_in_deck=dict.fromkeys(iterAllCards(), True), 
            players=[], 
            public_zone=[[None] * 4 for _ in range(3)], 
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
        cards_in_deck = []
        for idx in iterAllCards():
            cards_in_deck.append('t' if self.cards_in_deck[idx] else 'f')
        d['cards_in_deck'] = cards_in_deck
        d['players'] = [player.toPrimitive() for player in self.players]
        d['public_zone'] = [[
            card and card.toPrimitive() for card in row
        ] for row in self.public_zone]
        return d
    
    @classmethod
    def fromPrimitive(cls, d: dict):
        cards_in_deck: tp.Dict[tp.Tuple[int, int, int, int], bool] = {}
        for idx, char in zip(iterAllCards(), d['cards_in_deck']):
            cards_in_deck[idx] = char == 't'
        return cls(
            cards_in_deck=cards_in_deck, 
            players=[Player.fromPrimitive(player) for player in d['players']], 
            public_zone=[[
                card and SmartCard.fromPrimitive(card) for card in row
            ] for row in d['public_zone']],
        )
    
    def seekPlayer(self, uuid: str):
        for player in self.players:
            if player.uuid == uuid:
                return player
        raise KeyError(f'{uuid} not present')

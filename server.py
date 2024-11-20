from __future__ import annotations

import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import random
import time
import copy
import io
import traceback
import gzip
from functools import cached_property

from uuid import uuid4

from shared import *
from shared import (
    ServerEventType as SET, ServerEventField as SEF,
    ClientEventType as CET, ClientEventField as CEF, 
)
from gamestate import *

class HashMismatchError(Exception): pass
class JustWarnSourceUser(Exception): pass

class UndoTape:
    def __init__(self, max_size: int = 64):
        self.max_size = max_size
        self.tape: tp.List[Gamestate] = []
    
    def recordNewState(self, gamestate: Gamestate):
        self.tape.append(copy.deepcopy(gamestate))
        if len(self.tape) > self.max_size:
            self.tape.pop(0)
    
    def undo(self, current: Gamestate):
        try:
            memory = self.tape.pop()
        except IndexError:
            print('Warning: undo failed --- tape is empty')
            return current
        if memory.getUuids() != current.getUuids():
            print('Warning: undo failed --- undo past player join/leave is not supported')
            self.tape.clear()
            return current
        return memory

class Server:
    def __init__(self):
        self.port = int(input('Port > '))
        self.gamestate = Gamestate.default()
        self.undoTape = UndoTape()
        self.undoTape.recordNewState(self.gamestate)
        self.writers: tp.Dict[str, StreamWriter] = {}
        self.time_of_last_harvest = time.time()

    async def handleClient(self, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f'New connection from {addr}')
        try:
            handshake = await recvPrimitive(reader)
        except Exception as e:
            handshake = None
            print(f'Someone didn\'t handshake and caused {e}. Duh.')
        if handshake != HANDSHAKE:
            print(f'Handshake failed for {addr} --- expected {HANDSHAKE}, got {handshake}')
            writer.close()
            return
        uuid = str(uuid4())
        print(f'Assigning UUID {uuid[:4]}')
        await self.onPlayerJoin(uuid, writer)
        
        try:
            while True:
                try:
                    event = await recvPrimitive(reader)
                    try:
                        await self.handleEvent(uuid, event)
                    except JustWarnSourceUser as e:
                        payload = self.popupPayload('Warning', str(e))
                        sendPayload(payload, writer)
                except (
                    asyncio.IncompleteReadError, 
                    BrokenPipeError, 
                    ConnectionAbortedError, ConnectionResetError, 
                ):
                    print(f'Client {addr} disconnected')
                    break
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {uuid[:4]}')
        except Exception as e:
            print(f'Uncaught error with {uuid[:4]}: {e}')
            input('Press Enter to see exception and resume serving...')
            traceback.print_exc()
        finally:
            await self.onPlayerLeave(uuid)
            print(f'Closing connection with {uuid[:4]} ({addr})...')
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError):
                pass
            print('ok')

    async def start(self):
        print(f'Starting server on port {self.port}...')
        print('I\'m ready for client connections!')
        server = await asyncio.start_server(self.handleClient, '', self.port)

        async with server:
            try:
                await server.serve_forever()
            except asyncio.CancelledError:
                print('server closing...')
        print('ok')
    
    def gamestatePacket(self):
        self.gamestate.validate()
        return primitiveToPayload({
            SEF.TYPE: SET.GAMESTATE,
            SEF.CONTENT: self.gamestate.toPrimitive(), 
        })

    async def sendGamestate(
        self, writer: StreamWriter, cached_payload: bytes | None = None, 
    ):
        await sendPayload(cached_payload or self.gamestatePacket(), writer)
    
    async def broadcastGamestate(self):
        payload = self.gamestatePacket()
        await self.broadcast(payload)
        # re-encode gamestate for server-client hash consistency
        # self.gamestate = Gamestate.fromPrimitive(
        #     json.loads(json.dumps(
        #         self.gamestate.toPrimitive(), 
        #     )),
        # )
    
    async def broadcast(self, payload: bytes):
        for uuid, writer in [*self.writers.items()]:    # in case of concurrent modification
            try:
                await self.sendGamestate(writer, payload)
            except Exception as e:
                print('broadcast failed on', uuid, ':', e)
                continue
    
    async def onPlayerJoin(self, uuid: str, writer: StreamWriter):
        await sendPrimitive({
            SEF.TYPE: SET.YOU_ARE,
            SEF.CONTENT: uuid,
        }, writer)
        await streamPayload(self.texture, writer)
        self.writers[uuid] = writer
        self.gamestate.players.append(Player(
            str(uuid), f'Player {len(self.gamestate.players)}', 
            f'{random.randint(0, 100)},{random.randint(0, 100)},{random.randint(0, 100)}', 
        ))
        await self.broadcastGamestate()
    
    @cached_property
    def texture(self):
        try:
            with open(PNG, 'rb') as f:
                return gzip.compress(f.read())
        except FileNotFoundError:
            input('Hint: Did you run rasterize.py? Press Enter to see exception...')
            raise
    
    async def onPlayerLeave(self, uuid: str):
        self.writers.pop(uuid)
        self.gamestate.players = [p for p in self.gamestate.players if p.uuid != uuid]
        self.gamestate.validate()
        await self.broadcastGamestate()
    
    def checkHash(self, event: dict):
        if event[CEF.HASH] != self.gamestate.mutableHash():
            print('Gamestate hash mismatch. Dropping client event:', event[CEF.TYPE])
            raise HashMismatchError()
    
    async def handleEvent(self, uuid: str, event: dict):
        type_ = CET(event[CEF.TYPE])
        myself = self.gamestate.seekPlayer(uuid)
        print(f'client event: "{myself.name}" {type_.value}')
        try:
            if   type_ == CET.VOTE:
                # self.checkHash(event)
                myself.voting = Vote(event[CEF.VOTE])
                if (
                    myself.voting == Vote.ACCEPT and 
                    self.gamestate.uniqueShoutSetPlayer() is None
                ):
                    myself.voting = Vote.IDLE
                if not await self.resolveVotes():
                    return
            elif type_ == CET.CALL_SET:
                # self.checkHash(event)
                myself.shouted_set = time.time() - self.time_of_last_harvest
                self.gamestate.clearVoteAccept()
            elif type_ == CET.CANCEL_CALL_SET:
                # self.checkHash(event)
                myself.shouted_set = None
                self.gamestate.clearVoteAccept()
            elif type_ == CET.CHANGE_NAME:
                value = event[CEF.TARGET_VALUE]
                assert isinstance(value, str)
                myself.name = value
                print(f'{uuid[:4]} changed name to "{value}"')
            elif type_ == CET.CHANGE_COLOR:
                value = event[CEF.TARGET_VALUE]
                assert isinstance(value, str)
                try:
                    r, g, b = [int(x.strip()) for x in value.split(',')]
                    assert r in range(256)
                    assert g in range(256)
                    assert b in range(256)
                except Exception as e:
                    print(f'Warning: {uuid[:4]} submitted invalid color: "{value}", resulting in {e}')
                    return
                myself.color = f'{r},{g},{b}'
            elif type_ == CET.TOGGLE_DISPLAY_CASE_VISIBLE:
                target_uuid = event[CEF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                player.display_case_hidden = not player.display_case_hidden
            elif type_ == CET.ACC_N_WINS:
                target_uuid = event[CEF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                value = event[CEF.TARGET_VALUE]
                assert isinstance(value, int)
                player.n_of_wins += value
            elif type_ == CET.ACC_PUBLIC_ZONE_SHAPE:
                value = event[CEF.TARGET_VALUE]
                self.reshapePublicZone(*value)
            elif type_ == CET.TOGGLE_SELECT_CARD_PUBLIC:
                x, y = event[CEF.TARGET_VALUE]
                assert isinstance(x, int) and isinstance(y, int)
                card = self.gamestate.public_zone[x][y]
                if card is None:
                    # print(f'Warning: {uuid[:4]} tried to toggle an empty card slot in public zone')
                    return
                card.toggle(uuid)
                self.gamestate.clearVoteAccept()
            elif type_ == CET.TOGGLE_SELECT_CARD_DISPLAY:
                target_uuid = event[CEF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                x = event[CEF.TARGET_VALUE]
                assert isinstance(x, int)
                card = player.display_case[x]
                if card is None:
                    # print(f'Warning: {uuid[:4]} tried to toggle an empty card slot in display case')
                    return
                card.toggle(uuid)
                self.gamestate.clearVoteAccept()
            elif type_ == CET.CLEAR_MY_SELECTIONS:
                for card in self.gamestate.AllSmartCards():
                    if uuid in card.selected_by:
                        card.selected_by.remove(uuid)
            elif type_ == CET.DEAL_CARD:
                # self.checkHash(event) # checking hash would prevent rapid dealing.
                remaining: tp.List[Card] = []
                for idx in iterAllCards():
                    if self.gamestate.cards_in_deck[idx]:
                        remaining.append(idx)
                if not remaining:
                    print(f'Warning: {uuid[:4]} tried to deal a card from the empty deck')
                    return
                vacant = None
                for y, row in enumerate(self.gamestate.public_zone):
                    for x, card in enumerate(row):
                        if card is None:
                            vacant = (x, y)
                            break
                    else:
                        continue
                    break
                if vacant is None:
                    print(f'Warning: {uuid[:4]} tried to deal a card into the full public zone')
                    return
                card = random.choice(remaining)
                self.gamestate.cards_in_deck[card] = False
                self.gamestate.public_zone[vacant[1]][vacant[0]] = SmartCard(
                    card, time.time(), 
                )
            elif type_ == CET.PING:
                await sendPrimitive({
                    SEF.TYPE: SET.PONG,
                }, self.writers[uuid])
                return
            elif type_ == CET.TAKE:
                # self.checkHash(event)
                if not self.harvest(uuid):
                    return
            else:
                raise ValueError(f'Unknown event type: {type_}')
            await self.broadcast(self.gamestatePacket())
        except HashMismatchError:
            pass
    
    def reshapePublicZone(self, acc_n_rows: int, acc_n_cols: int):
        zone = self.gamestate.public_zone
        n_cards = 0
        old_n_rows = len(zone)
        old_n_cols = len(zone[0])
        for row in zone:
            for card in row:
                if card is not None:
                    n_cards += 1
        new_n_rows = old_n_rows + acc_n_rows
        new_n_cols = old_n_cols + acc_n_cols
        if new_n_rows * new_n_cols < n_cards:
            print('Warning: someone attempted to shrink public zone at capacity')
            return
        stashed = []
        for y, row in enumerate(zone):
            for x, card in enumerate(row):
                if card is None:
                    continue
                if x >= new_n_cols or y >= new_n_rows:
                    stashed.append(card)
            if new_n_cols < old_n_cols:
                zone[y] = row[:new_n_cols]
            else:
                row.extend([None] * (new_n_cols - old_n_cols))
        if new_n_rows < old_n_rows:
            zone = zone[:new_n_rows]
        else:
            zone.extend([[None] * new_n_cols for _ in range(new_n_rows - old_n_rows)])
        for row in zone:
            for x, card in enumerate(row):
                if card is None:
                    try:
                        row[x] = stashed.pop(0)
                    except IndexError:
                        break
            else:
                continue
            break
        assert not stashed
        self.gamestate.public_zone = zone
    
    async def resolveVotes(self):
        votes: tp.Set[Vote] = set()
        for player in self.gamestate.players:
            votes.add(player.voting)
        
        if len(votes) != 1:
            return
        consensus = votes.pop()
        for player in self.gamestate.players:
            player.voting = Vote.IDLE
        if consensus == Vote.IDLE:
            return
        elif consensus == Vote.NEW_GAME:
            self.undoTape.recordNewState(self.gamestate)
            self.gamestate.cards_in_deck = Gamestate.fullDeck()
            for row in self.gamestate.public_zone:
                for i in range(len(row)):
                    row[i] = None
            for player in self.gamestate.players:
                player.voting = Vote.IDLE
                player.shouted_set = None
                player.wealth_thickness = 0
                player.display_case = Player.newDisplayCase()
            self.time_of_last_harvest = time.time()
        elif consensus == Vote.UNDO:
            self.time_of_last_harvest = time.time()
            self.gamestate = self.undoTape.undo(self.gamestate)
        elif consensus == Vote.ACCEPT:
            winner = self.gamestate.uniqueShoutSetPlayer()
            assert winner is not None
            return self.harvest(winner.uuid)
        elif consensus == Vote.COUNT_CARDS:
            buf = io.StringIO()
            for player in self.gamestate.players:
                score = player.wealth_thickness + len(
                    [x for x in player.display_case if x is not None]
                )
                print(player.name, ':', score, file=buf)
            buf.seek(0)
            payload = self.popupPayload('Count cards', buf.read())
            await self.broadcast(payload)
        else:
            raise ValueError(f'Unknown vote: {consensus}')
        return True
    
    def popupPayload(self, title: str, content: str):
        return primitiveToPayload({
            SEF.TYPE: SET.POPUP_MESSAGE,
            SEF.CONTENT: (title, content),
        })
    
    def harvest(self, taker_uuid: str):
        self.undoTape.recordNewState(self.gamestate)
        taker = self.gamestate.seekPlayer(taker_uuid)
        the_set: tp.List[SmartCard] = []
        for row in self.gamestate.public_zone:
            for i, card in enumerate(row):
                if card is None:
                    continue
                if taker_uuid in card.selected_by:
                    the_set.append(card)
                    row[i] = None
        for player in self.gamestate.players:
            taken = False
            for i, card in enumerate(player.display_case):
                if card is None:
                    continue
                if taker_uuid in card.selected_by:
                    the_set.append(card)
                    taken = True
                    player.display_case[i] = None
            if taken or player.uuid == taker_uuid:
                for card in player.display_case:
                    if card is not None:
                        taker.wealth_thickness += 1
                player.display_case = Player.newDisplayCase()
        if not the_set:
            self.gamestate = self.undoTape.undo(self.gamestate)
            return False
        for i, card in enumerate(the_set):
            card.selected_by.clear()
            card.birth = time.time()
            try:
                taker.display_case[i] = card
            except IndexError:
                print('Error: tried to take more than 4 cards into display case')
                break
        self.time_of_last_harvest = time.time()
        for player in self.gamestate.players:
            player.shouted_set = None
        return True

def main():
    server = Server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print('bye')

if __name__ == '__main__':
    main()

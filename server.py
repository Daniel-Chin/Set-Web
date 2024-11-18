from __future__ import annotations

import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import random
import time
import copy
import io
import traceback

from uuid import uuid4

from shared import *
from shared import (
    ServerEventType as SET, ServerEventField as SEF,
    ClientEventType as CET, ClientEventField as CEF, 
)
from gamestate import *

class HashMismatchError(Exception): pass

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
        uuid = str(uuid4())
        print(f'New connection from {addr}')
        print(f'Assigning UUID {uuid}')
        self.writers[uuid] = writer
        await self.onPlayerJoin(uuid)
        
        try:
            while True:
                try:
                    event = await recvPrimitive(reader)
                except asyncio.IncompleteReadError:
                    print(f'Client {addr} disconnected')
                    await self.onPlayerLeave(uuid)
                    break
                await self.handleEvent(uuid, event)
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {addr}')
        except Exception as e:
            print(f'Error with client {addr}: {e}')
            traceback.print_exc()
        finally:
            print(f'Closing connection to {addr}...')
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError):
                pass
            print('ok')

    async def start(self):
        print(f'Starting server on port {self.port}')
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
        for uuid, writer in self.writers.items():
            try:
                await self.sendGamestate(writer, payload)
            except Exception as e:
                print('broadcast failed on', uuid, ':', e)
                continue
    
    async def onPlayerJoin(self, uuid: str):
        self.gamestate.players.append(Player(
            str(uuid), f'Player {len(self.gamestate.players)}', 
            f'{random.randint(0, 100)},{random.randint(0, 100)},{random.randint(0, 100)}', 
        ))
        writer = self.writers[uuid]
        await sendPrimitive({
            SEF.TYPE: SET.YOU_ARE,
            SEF.CONTENT: uuid,
        }, writer)
        await self.broadcastGamestate()
    
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
        try:
            if   type_ == CET.VOTE:
                self.checkHash(event)
                myself.voting = Vote(event[CEF.VOTE])
                if (
                    myself.voting == Vote.ACCEPT and 
                    self.gamestate.uniqueShoutSetPlayer() is None
                ):
                    myself.voting = Vote.IDLE
                await self.resolveVotes()
            elif type_ == CET.CALL_SET:
                self.checkHash(event)
                myself.shouted_set = time.time() - self.time_of_last_harvest
                self.gamestate.clearVoteAccept()
            elif type_ == CET.CANCEL_CALL_SET:
                self.checkHash(event)
                myself.shouted_set = None
                self.gamestate.clearVoteAccept()
            elif type_ == CET.CHANGE_NAME:
                value = event[CEF.TARGET_VALUE]
                assert isinstance(value, str)
                myself.name = value
            elif type_ == CET.CHANGE_COLOR:
                value = event[CEF.TARGET_VALUE]
                assert isinstance(value, str)
                try:
                    r, g, b = [int(x.strip()) for x in value.split(',')]
                    assert r in range(256)
                    assert g in range(256)
                    assert b in range(256)
                except Exception as e:
                    print(f'Warning: {uuid} submitted invalid color: "{value}", resulting in {e}')
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
                    # print(f'Warning: {uuid} tried to toggle an empty card slot in public zone')
                    return
                card.toggle(uuid)
                self.gamestate.clearVoteAccept()
            elif type_ == CET.TOGGLE_SELECT_CARD_DISPLAY:
                target_uuid = event[CEF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                x = event[CEF.TARGET_VALUE]
                assert isinstance(x, int)
                try:
                    card = player.display_case[x]
                except IndexError:
                    # print(f'Warning: {uuid} tried to toggle an empty card slot in display case')
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
                    print(f'Warning: {uuid} tried to deal a card from the empty deck')
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
                    print(f'Warning: {uuid} tried to deal a card into the full public zone')
                    return
                card = random.choice(remaining)
                self.gamestate.cards_in_deck[card] = False
                self.gamestate.public_zone[vacant[1]][vacant[0]] = SmartCard(
                    card, time.time(), 
                )
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
        # dont forget to set self.time_of_last_harvest
        votes: tp.Set[Vote] = set()
        for players in self.gamestate.players:
            votes.add(players.voting)
        if len(votes) != 1:
            return
        consensus = votes.pop()
        for winner in self.gamestate.players:
            winner.voting = Vote.IDLE
        if consensus == Vote.IDLE:
            return
        elif consensus == Vote.NEW_GAME:
            self.undoTape.recordNewState(self.gamestate)
            self.gamestate.cards_in_deck = Gamestate.fullDeck()
            for row in self.gamestate.public_zone:
                for i in range(len(row)):
                    row[i] = None
            for winner in self.gamestate.players:
                winner.voting = Vote.IDLE
                winner.shouted_set = None
                winner.wealth_thickness = 0
                winner.display_case.clear()
            self.time_of_last_harvest = time.time()
        elif consensus == Vote.UNDO:
            self.time_of_last_harvest = time.time()
            self.gamestate = self.undoTape.undo(self.gamestate)
        elif consensus == Vote.ACCEPT:
            self.undoTape.recordNewState(self.gamestate)
            winner = self.gamestate.uniqueShoutSetPlayer()
            assert winner is not None
            the_set: tp.List[SmartCard] = []
            for row in self.gamestate.public_zone:
                for i, card in enumerate(row):
                    if card is None:
                        continue
                    if winner.uuid in card.selected_by:
                        the_set.append(card)
                        row[i] = None
            for player in self.gamestate.players:
                for card in player.display_case:
                    if winner.uuid in card.selected_by:
                        the_set.append(card)
                    else:
                        winner.wealth_thickness += 1
                player.display_case.clear()
            for card in the_set:
                card.selected_by.remove(winner.uuid)
                card.birth = time.time()
                winner.display_case.append(card)
            self.time_of_last_harvest = time.time()
            for player in self.gamestate.players:
                player.shouted_set = None
        elif consensus == Vote.COUNT_CARDS:
            buf = io.StringIO()
            for player in self.gamestate.players:
                score = player.wealth_thickness + len(player.display_case)
                print(player.name, ':', score, file=buf)
            buf.seek(0)
            payload = primitiveToPayload({
                SEF.TYPE: SET.POPUP_MESSAGE,
                SEF.CONTENT: ('Count cards', buf.read()),
            })
            await self.broadcast(payload)
        else:
            raise ValueError(f'Unknown vote: {consensus}')

def main():
    server = Server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print('bye')

if __name__ == '__main__':
    main()

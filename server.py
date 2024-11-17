import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import random
import time

from uuid import uuid4

from shared import *
from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

class HashMismatchError(Exception): pass

class Server:
    def __init__(self):
        self.port = int(input('Port > '))
        self.gamestate = Gamestate.default()
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
                    self.writers.pop(uuid)
                    await self.broadcastGamestate()
                    break
                await self.handleEvent(uuid, event)
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {addr}')
        except Exception as e:
            print(f'Error with client {addr}: {e}')
        finally:
            print(f'Closing connection to {addr}...')
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionResetError:
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
        return primitiveToPayload(
            self.gamestate.toPrimitive(), 
        )

    def sendGamestate(
        self, writer: StreamWriter, cached_payload: bytes | None = None, 
    ):
        sendPayload(cached_payload or self.gamestatePacket(), writer)
    
    async def broadcastGamestate(self):
        payload = self.gamestatePacket()
        for uuid, writer in self.writers.items():
            try:
                self.sendGamestate(writer, payload)
                # await writer.drain()
            except Exception as e:
                print('broadcast failed on', uuid, ':', e)
                continue
    
    async def onPlayerJoin(self, uuid: str):
        self.gamestate.players.append(Player(
            str(uuid), f'Player {len(self.gamestate.players)}', 
            f'{random.randint(0, 255)},{random.randint(0, 255)},{random.randint(0, 255)}', 
        ))
        writer = self.writers[uuid]
        sendPrimitive(uuid, writer)
        self.sendGamestate(writer)
        # await writer.drain()
        self.gamestate.validate()
    
    async def onPlayerLeave(self, uuid: str):
        self.gamestate.players = [p for p in self.gamestate.players if p.uuid != uuid]
        self.gamestate.validate()
    
    def checkHash(self, event: dict):
        if event[EF.HASH] != self.gamestate.mutableHash():
            print('Gamestate hash mismatch. Dropping client event:', event[EF.TYPE])
            raise HashMismatchError()
    
    async def handleEvent(self, uuid: str, event: dict):
        type_ = ET(event[EF.TYPE])
        myself = self.gamestate.seekPlayer(uuid)
        try:
            if   type_ == ET.VOTE:
                self.checkHash(event)
                myself.voting = Vote(event[EF.VOTE])
                ... # voting logic
                # dont forget to set self.time_of_last_harvest
            elif type_ == ET.CALL_SET:
                self.checkHash(event)
                myself.shouted_set = time.time() - self.time_of_last_harvest
            elif type_ == ET.CANCEL_CALL_SET:
                self.checkHash(event)
                myself.shouted_set = None
            elif type_ == ET.CHANGE_NAME:
                value = event[EF.TARGET_VALUE]
                assert isinstance(value, str)
                myself.name = value
            elif type_ == ET.CHANGE_COLOR:
                value = event[EF.TARGET_VALUE]
                assert isinstance(value, str)
                myself.color = value
            elif type_ == ET.TOGGLE_DISPLAY_CASE_VISIBLE:
                target_uuid = event[EF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                player.display_case_hidden = not player.display_case_hidden
            elif type_ == ET.ACC_N_WINS:
                target_uuid = event[EF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                value = event[EF.TARGET_VALUE]
                assert isinstance(value, int)
                player.n_of_wins += value
            elif type_ == ET.ACC_PUBLIC_ZONE_SHAPE:
                value = event[EF.TARGET_VALUE]
                self.reshapePublicZone(*value)
            elif type_ == ET.TOGGLE_SELECT_CARD_PUBLIC:
                x, y = event[EF.TARGET_VALUE]
                assert isinstance(x, int) and isinstance(y, int)
                card = self.gamestate.public_zone[x][y]
                if card is None:
                    print(f'Warning: {myself} tried to toggle an empty card slot')
                    return
                card.toggle(uuid)
            elif type_ == ET.TOGGLE_SELECT_CARD_DISPLAY:
                target_uuid = event[EF.TARGET_PLAYER]
                player = self.gamestate.seekPlayer(target_uuid)
                x = event[EF.TARGET_VALUE]
                assert isinstance(x, int)
                card = player.display_case[x]
                card.toggle(uuid)
            await self.broadcastGamestate()
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
            zone[y] = row[:new_n_cols]
        zone = zone[:new_n_rows]
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

def main():
    server = Server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print('bye')

if __name__ == '__main__':
    main()

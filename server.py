import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import gzip
import json
import random
import time

from uuid import uuid4

from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

class Server:
    def __init__(self):
        self.port = int(input('Port > '))
        self.gamestate = Gamestate.default()
        self.clients: tp.Dict[str, StreamWriter] = {}
        self.time_of_last_harvest = time.time()

    async def handleClient(self, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info('peername')
        uuid = str(uuid4())
        print(f'New connection from {addr}')
        print(f'Assigning UUID {uuid}')
        self.clients[uuid] = writer
        await self.onPlayerJoin(uuid)
        
        try:
            while True:
                data = await reader.readuntil('\x00')
                if not data:
                    print(f'Connection closed by {addr}')
                    break
                
                event = json.loads(gzip.decompress(data[:-1]).decode())
                self.handleEvent(uuid, event)
                await self.broadcastGamestate()
        
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {addr}')
        except Exception as e:
            print(f'Error with client {addr}: {e}')
        finally:
            await self.onPlayerLeave(uuid)
            print(f'Closing connection to {addr}... ', end='', flush=True)
            self.clients.pop(uuid)
            writer.close()
            await self.broadcastGamestate()
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
                print('server closing... ', end='', flush=True)
        print('ok')
    
    def gamestatePacket(self):
        self.gamestate.validate()
        payload = gzip.compress(json.dumps(
            self.gamestate.toPrimitive(), 
        ).encode()) + b'\x00'
        return payload

    def sendGamestate(
        self, writer: StreamWriter, cached_payload: bytes | None = None, 
    ):
        writer.write(cached_payload or self.gamestatePacket())
    
    async def broadcastGamestate(self):
        payload = self.gamestatePacket()
        for uuid, writer in self.clients.items():
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
        writer = self.clients[uuid]
        writer.write(json.dumps(uuid).encode() + b'\x00')
        self.sendGamestate(writer)
        # await writer.drain()
    
    async def onPlayerLeave(self, uuid: str):
        self.gamestate.players = [p for p in self.gamestate.players if p.uuid != uuid]
    
    async def handleEvent(self, uuid: str, event: dict):
        type_ = event[EF.TYPE]
        if event[EF.HASH] != hash(self.gamestate):
            print('Gamestate hash mismatch. Dropping client event:', type_)
            return
        if   type_ == ET.VOTE:
            self.gamestate.seekPlayer(uuid).voting = Vote(event[EF.VOTE])
            ... # voting logic
            # dont forget to set self.time_of_last_harvest
        elif type_ == ET.CALL_SET:
            self.gamestate.seekPlayer(uuid).shouted_set = time.time() - self.time_of_last_harvest
        elif type_ == ET.CANCEL_CALL_SET:
            self.gamestate.seekPlayer(uuid).shouted_set = None
        await self.broadcastGamestate()

def main():
    server = Server()
    asyncio.run(server.start())

if __name__ == '__main__':
    main()

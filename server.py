import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import gzip
import json
import random

from uuid import uuid4, UUID

from gamestate import *

class Server:
    def __init__(self):
        self.port = int(input('Port > '))
        self.gamestate = Gamestate()
        self.clients: tp.Dict[UUID, StreamWriter] = {}

    async def handleClient(self, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info('peername')
        uuid = uuid4()
        print(f'New connection from {addr}')
        print(f'Assigning UUID {uuid}')
        self.clients[uuid] = writer
        self.onPlayerJoin(uuid)
        
        try:
            while True:
                data = await reader.readuntil('\x00')
                if not data:
                    print(f'Connection closed by {addr}')
                    break
                
                event = json.loads(gzip.decompress(data[:-1]).decode())
                ...
                await self.broadcastGamestate()
        
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {addr}')
        except Exception as e:
            print(f'Error with client {addr}: {e}')
        finally:
            self.onPlayerLeave(uuid)
            print(f'Closing connection to {addr}... ', end='', flush=True)
            self.clients.pop(uuid)
            writer.close()
            await self.broadcastGamestate()
            await writer.wait_closed()
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
    
    async def broadcastGamestate(self):
        for uuid, writer in self.clients.items():
            try:
                writer.write(gzip.compress(json.dumps(
                    self.gamestate.toPrimitive(), 
                ).encode()) + b'\x00')
                # await writer.drain()
            except Exception as e:
                print('broadcast failed on', uuid, ':', e)
                continue
    
    async def onPlayerJoin(self, uuid: UUID):
        self.gamestate.players.append(Player(
            uuid, f'Player {len(self.gamestate.players)}', 
            f'{random.randint(0, 255)},{random.randint(0, 255)},{random.randint(0, 255)}', 
        ))
    
    async def onPlayerLeave(self, uuid: UUID):
        self.gamestate.players = [p for p in self.gamestate.players if p.uuid != uuid]

def main():
    server = Server()
    asyncio.run(server.start())

if __name__ == '__main__':
    main()

import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter
import random
import time

from uuid import uuid4

from shared import *
from shared import ClientEventType as ET, ClientEventFields as EF
from gamestate import *

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
                self.handleEvent(uuid, event)
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
    
    async def onPlayerLeave(self, uuid: str):
        self.gamestate.players = [p for p in self.gamestate.players if p.uuid != uuid]
    
    async def handleEvent(self, uuid: str, event: dict):
        type_ = event[EF.TYPE]
        if event[EF.HASH] != self.gamestate.mutableHash():
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
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print('bye')

if __name__ == '__main__':
    main()

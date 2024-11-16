import typing as tp
import asyncio
from asyncio import StreamReader, StreamWriter

from uuid import uuid4, UUID

from gamestate import Gamestate

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
        
        try:
            while True:
                data = await reader.readuntil('\x00')
                if not data:
                    print(f'Connection closed by {addr}')
                    break
                
                message = data[:-1].decode()
                ...
        
        except asyncio.CancelledError:
            print(f'Client handler task cancelled for {addr}')
        except Exception as e:
            print(f'Error with client {addr}: {e}')
        finally:
            print(f'Closing connection to {addr}... ', end='', flush=True)
            self.clients.pop(uuid)
            writer.close()
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

def main():
    server = Server()
    asyncio.run(server.start())

if __name__ == '__main__':
    main()

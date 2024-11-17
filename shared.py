import typing as tp
import random
import os
from enum import Enum
import gzip
import json
import asyncio
from hashlib import sha256

import tkinter as tk
import tkinter.ttk as ttk

PACKET_LEN_PREFIX_LEN = 8

Card = tp.Tuple[int, int, int, int]

CARD_ASPECT = (43, 62)

def boolsToBytes(bools: tp.Iterator[bool]) -> bytes:
    byte_array = bytearray()
    current_byte = 0
    bit_count = 0

    for bit in bools:
        current_byte = (current_byte << 1) | int(bit)
        bit_count += 1
        if bit_count == 8:
            byte_array.append(current_byte)
            current_byte = 0
            bit_count = 0

    if bit_count > 0:
        current_byte <<= (8 - bit_count)
        byte_array.append(current_byte)

    return bytes(byte_array)

def bytesToBools(b: bytes, /) -> tp.Iterator[bool]:
    for byte in b:
        for bit_pos in range(7, -1, -1):
            yield (byte >> bit_pos) & 1 == 1

def testBitsConversion():
    for _ in range(100):
        n = random.randint(1, 256)
        bytes_ = os.urandom(n)
        assert boolsToBytes(bytesToBools(bytes_)) == bytes_

        bool_list = [random.choice([True, False]) for _ in range(n)]
        packed_bytes = boolsToBytes(iter(bool_list))
        unpacked_bools = list(bytesToBools(packed_bytes))[:n]
        assert bool_list == unpacked_bools

def iterAllCards():
    for c in range(3):
        for f in range(3):
            for n in range(3):
                for s in range(3):
                    yield (c, f, n, s)

class Vote(str, Enum):
    IDLE = 'IDLE'
    NEW_GAME = 'NEW_GAME'
    ACCEPT = 'ACCEPT'
    UNDO = 'UNDO'
    COUNT_CARDS = 'COUNT_CARDS'

class ServerEventField(str, Enum):
    TYPE = 'type'
    CONTENT = 'content'

class ServerEventType(str, Enum):
    GAMESTATE = 'GAMESTATE'
    YOU_ARE = 'YOU_ARE'
    POPUP_MESSAGE = 'POPUP_MESSAGE'

class ClientEventField(str, Enum):
    TYPE = 'type'
    HASH = 'gamestate_hash'
    VOTE = 'vote'
    TARGET_VALUE = 'target_value'
    TARGET_PLAYER = 'target_player'

class ClientEventType(str, Enum):
    VOTE = 'VOTE'
    CALL_SET = 'CALL_SET'
    CANCEL_CALL_SET = 'CANCEL_CALL_SET'
    CHANGE_NAME = 'CHANGE_NAME'
    CHANGE_COLOR = 'CHANGE_COLOR'
    TOGGLE_DISPLAY_CASE_VISIBLE = 'TOGGLE_DISPLAY_CASE_VISIBLE'
    ACC_N_WINS = 'ACC_N_WINS'
    ACC_PUBLIC_ZONE_SHAPE = 'ACC_PUBLIC_ZONE_SHAPE'
    TOGGLE_SELECT_CARD_PUBLIC = 'TOGGLE_SELECT_CARD_PUBLIC'
    TOGGLE_SELECT_CARD_DISPLAY = 'TOGGLE_SELECT_CARD_DISPLAY'
    CLEAR_MY_SELECTIONS = 'CLEAR_MY_SELECTIONS'
    DEAL_CARD = 'DEAL_CARD'

async def sendPayload(payload: bytes, writer: asyncio.StreamWriter):
    prefix = format(len(payload), f'0{PACKET_LEN_PREFIX_LEN}d').encode()
    assert len(prefix) <= PACKET_LEN_PREFIX_LEN
    writer.write(prefix)
    writer.write(payload)
    await writer.drain()

def primitiveToPayload(x, /):
    payload = gzip.compress(json.dumps(x).encode())
    return payload

async def sendPrimitive(x, /, writer: asyncio.StreamWriter):
    await sendPayload(primitiveToPayload(x), writer)

async def recvPrimitive(reader: asyncio.StreamReader):
    prefix = await reader.readexactly(PACKET_LEN_PREFIX_LEN)
    payload_len = int(prefix)
    payload = await reader.readexactly(payload_len)
    return json.loads(gzip.decompress(payload))

def deterministicHash(x: tp.Any, /):
    return sha256(json.dumps(x).encode()).hexdigest()

def disableIf(button: tk.Button | ttk.Button, condition: bool):
    if condition:
        button.config(state=tk.DISABLED)
    else:
        button.config(state=tk.NORMAL)

def rgbToHex(r: int, g: int, b: int):
    return f'#{r:02x}{g:02x}{b:02x}'

def rgbStrToHex(x: str, /):
    return rgbToHex(*[int(e) for e in x.split(',')])

if __name__ == '__main__':
    testBitsConversion()
    print('ok')

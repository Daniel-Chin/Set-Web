import typing as tp
import random
import os
from enum import Enum

Card = tp.Tuple[int, int, int, int]

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

class Vote(Enum):
    IDLE = 'IDLE'
    NEW_GAME = 'NEW_GAME'
    ACCEPT = 'ACCEPT'
    UNDO = 'UNDO'

class ClientEventFields(Enum):
    TYPE = 'type'
    HASH = 'gamestate_hash'
    VOTE = 'vote'

class ClientEventType(Enum):
    VOTE = 'VOTE'
    CALL_SET = 'CALL_SET'
    CANCEL_CALL_SET = 'CANCEL_CALL_SET'

if __name__ == '__main__':
    testBitsConversion()
    print('ok')

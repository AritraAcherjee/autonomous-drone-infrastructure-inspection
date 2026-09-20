#!/usr/bin/env python3
"""Generate the project-authored P19 evaluation texture without input data."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import struct
import zlib

GENERATOR_VERSION = "P19-HONEYCOMB-PROCEDURAL-v1"
WIDTH = 512
HEIGHT = 512
SEED = 1903001


def _chunk(name: bytes, payload: bytes) -> bytes:
    body = name + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def pixels() -> bytes:
    rows = bytearray()
    holes = []
    for row in range(8):
        for column in range(9):
            x = 30 + column * 58 + (29 if row % 2 else 0)
            y = 34 + row * 63
            radius = 14 + ((row * 17 + column * 23 + SEED) % 8)
            holes.append((x, y, radius))
    for y in range(HEIGHT):
        rows.append(0)
        for x in range(WIDTH):
            base = 163 + ((x * 7 + y * 11 + SEED) % 19)
            value = [base, base - 9, base - 18]
            for hx, hy, radius in holes:
                distance = math.hypot(x - hx, y - hy)
                if distance < radius:
                    shade = int(34 + 46 * distance / radius)
                    value = [shade, max(0, shade - 5), max(0, shade - 9)]
                    break
                if distance < radius + 4:
                    value = [105, 96, 84]
                    break
            rows.extend(value)
    return bytes(rows)


def png_bytes() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return signature + _chunk(b"IHDR", header) + _chunk(
        b"tEXt", f"generator\0{GENERATOR_VERSION};seed={SEED}".encode()
    ) + _chunk(b"IDAT", zlib.compress(pixels(), 9)) + _chunk(b"IEND", b"")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = png_bytes()
    args.output.write_bytes(payload)
    print(hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()

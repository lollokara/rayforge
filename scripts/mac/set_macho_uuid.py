#!/usr/bin/env python3
"""
Give a Mach-O executable a new random LC_UUID.

PyInstaller's prebuilt bootloader carries the same LC_UUID in every app
built with it. macOS keys its Local Network state to that UUID, so apps
sharing it collide and a stale entry can block the permission prompt.
A unique UUID per build avoids that. Re-sign the bundle afterwards.

    python3 scripts/mac/set_macho_uuid.py PATH
"""
import struct
import sys
import uuid

MH_MAGIC_64 = 0xFEEDFACF
LC_UUID = 0x1B


def set_uuid(path: str) -> tuple[uuid.UUID, uuid.UUID]:
    with open(path, "r+b") as f:
        header = f.read(32)
        magic = struct.unpack_from("<I", header, 0)[0]
        ncmds = struct.unpack_from("<I", header, 16)[0]
        if magic != MH_MAGIC_64:
            raise SystemExit(f"{path}: not a 64-bit little-endian Mach-O")
        offset = 32
        for _ in range(ncmds):
            f.seek(offset)
            cmd, size = struct.unpack("<II", f.read(8))
            if cmd == LC_UUID:
                old = uuid.UUID(bytes=f.read(16))
                new = uuid.uuid4()
                f.seek(offset + 8)
                f.write(new.bytes)
                return old, new
            offset += size
    raise SystemExit(f"{path}: no LC_UUID load command")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    old_uuid, new_uuid = set_uuid(sys.argv[1])
    print(f"LC_UUID {old_uuid} -> {new_uuid}")

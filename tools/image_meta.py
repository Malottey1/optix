"""Metadata in an image file's own container: EXIF, XMP, ICC profiles and text chunks.

Reads PNG chunks, WebP RIFF chunks and JPEG markers directly (no decoder needed), so the brand
asset test and the web gate can prove shipped images carry none of it.
"""
from __future__ import annotations

import struct
from pathlib import Path


def metadata_chunks(p: Path) -> list[str]:
    """EXIF, XMP, ICC and text chunks found in the file's own container structure."""
    b = p.read_bytes()
    found = []
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        i = 8
        while i < len(b):
            n, kind = struct.unpack(">I4s", b[i:i + 8])
            if kind in (b"eXIf", b"iCCP", b"tEXt", b"iTXt", b"zTXt", b"tIME"):
                found.append(kind.decode())
            i += 12 + n
    elif b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(b):
            kind, n = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
            if kind in (b"EXIF", b"XMP ", b"ICCP"):
                found.append(kind.decode().strip())
            i += 8 + n + (n & 1)
    elif b[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(b) and b[i] == 0xFF:
            marker, n = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
            seg = b[i + 4:i + 4 + n - 2]
            if marker == 0xE1:
                found.append("APP1 (EXIF/XMP)")
            if marker == 0xE2 and seg.startswith(b"ICC_PROFILE"):
                found.append("ICC")
            if marker == 0xFE:
                found.append("COM")
            if marker == 0xDA:
                break
            i += 2 + n
    return found

"""Images made in memory with Pillow for the image upload tests (F13-h).

Nothing here touches a real image directory or the network.
"""
import io
import os
import struct
import zlib

from PIL import Image

RED = (220, 20, 20)
GREEN = (20, 200, 20)
BLUE = (20, 20, 220)


def encode(image, fmt, **params):
    buffer = io.BytesIO()
    image.save(buffer, fmt, **params)
    return buffer.getvalue()


def solid(size=(400, 560), color=GREEN, mode='RGB'):
    return Image.new(mode, size, color)


def png(size=(400, 560), color=GREEN, mode='RGB', **params):
    return encode(solid(size, color, mode), 'PNG', **params)


def jpeg(size=(400, 560), color=GREEN, **params):
    return encode(solid(size, color), 'JPEG', **params)


def webp(size=(400, 560), color=GREEN, **params):
    return encode(solid(size, color), 'WEBP', **params)


def halves(size, left, right):
    """`left` colour on the left half, `right` on the right half."""
    image = Image.new('RGB', size, left)
    width, height = size
    image.paste(right, (width // 2, 0, width, height))
    return image


def exif_with_gps(orientation):
    exif = Image.Exif()
    exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = 'N', (40.0, 26.0, 0.0), 'W', (3.0, 42.0, 0.0)
    return exif


def png_with_header_size(width, height):
    """A real small PNG whose IHDR claims `width` x `height` (the pixel data stays small)."""
    data = bytearray(png((64, 64)))
    ihdr = data.index(b'IHDR')
    data[ihdr + 4:ihdr + 12] = struct.pack('>II', width, height)
    crc = zlib.crc32(bytes(data[ihdr:ihdr + 17])) & 0xffffffff
    data[ihdr + 17:ihdr + 21] = struct.pack('>I', crc)
    return bytes(data)


def noise_png(min_bytes):
    """A valid PNG of random pixels at least `min_bytes` long (random data does not compress)."""
    side = int((min_bytes / 3) ** 0.5) + 16
    image = Image.frombytes('RGB', (side, side), os.urandom(side * side * 3))
    data = encode(image, 'PNG', compress_level=0)
    assert len(data) >= min_bytes
    return data


def opened(data):
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def close(pixel, color, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], color))

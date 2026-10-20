"""UUID version 7 (RFC 9562) — l'identifiant de toute entité (D145).
48 bits de temps en millisecondes, 12 bits aléatoires, 62 bits aléatoires : croissant dans le
temps, donc un index qui se remplit par la fin ; non devinable. Python 3.12 ne l'a pas."""
import os, time, uuid

def uuid7() -> uuid.UUID:
    ms = time.time_ns() // 1_000_000
    r = os.urandom(10)
    b = (ms.to_bytes(6, "big")
         + bytes([0x70 | (r[0] & 0x0F), r[1]])          # version 7 + 12 bits aléatoires
         + bytes([0x80 | (r[2] & 0x3F)]) + r[3:10])       # variante RFC + 62 bits aléatoires
    return uuid.UUID(bytes=b)

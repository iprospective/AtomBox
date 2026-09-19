#!/usr/bin/env python3
"""LES ICÔNES de l'application installée (RM3251, D172) — engendrées, sans bibliothèque d'image.

    python3 outils/icones.py        # réécrit icones/*.png

Une enveloppe blanche sur le bleu de l'interface (`--accent` de src/noyau/_base.scss). Dessinée
point par point, avec un sur-échantillonnage 4×4 pour que les bords ne soient pas crénelés ; écrite
en PNG à la main (zlib + CRC), parce qu'aucune bibliothèque d'image n'est installée et qu'une
dépendance de plus pour quatre fichiers serait une mauvaise affaire.

La variante « maskable » est celle qu'Android découpe à sa guise (cercle, carré arrondi, goutte) :
le dessin doit tenir dans le disque central de 80 % — la « zone de sécurité » —, et le fond couvrir
tout le carré. Sans elle, Android pose l'icône sur un fond blanc, rétrécie.

La sortie est REPRODUCTIBLE : mêmes octets à chaque exécution (aucune date dans le PNG).
"""
from __future__ import annotations
import math, os, struct, zlib

ACCENT = (0x2F, 0x6F, 0xED)
BLANC = (0xFF, 0xFF, 0xFF)
ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "icones")


def _rect_arrondi(x, y, x0, y0, x1, y1, r) -> bool:
    if not (x0 <= x <= x1 and y0 <= y <= y1): return False
    cx = min(max(x, x0 + r), x1 - r); cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def couleur(x: float, y: float, maskable: bool):
    """la couleur au point (x, y) du carré unité, ou None (transparent)"""
    # le fond : tout le carré pour « maskable » (Android découpe), un carré arrondi sinon
    if not maskable and not _rect_arrondi(x, y, 0.0, 0.0, 1.0, 1.0, 0.22): return None
    # l'enveloppe : plus petite en « maskable », pour tenir dans le disque de 80 %
    k = 0.72 if maskable else 1.0
    w, h = 0.62 * k, 0.44 * k
    x0, y0 = 0.5 - w / 2, 0.52 - h / 2
    x1, y1 = x0 + w, y0 + h
    if _rect_arrondi(x, y, x0, y0, x1, y1, 0.05 * k):
        # le rabat : un V du haut des bords vers le centre, tracé en bleu dans le blanc
        e = 0.045 * k
        if min(_segment(x, y, x0 + e, y0 + e, 0.5, y0 + h * 0.58),
               _segment(x, y, x1 - e, y0 + e, 0.5, y0 + h * 0.58)) < e * 0.62:
            return ACCENT
        return BLANC
    return ACCENT


def dessiner(taille: int, maskable: bool) -> bytes:
    n = 4                                            # sur-échantillonnage n×n
    lignes = []
    for j in range(taille):
        ligne = bytearray([0])                       # filtre PNG « aucun »
        for i in range(taille):
            r = g = b = a = 0
            for sj in range(n):
                for si in range(n):
                    c = couleur((i + (si + 0.5) / n) / taille, (j + (sj + 0.5) / n) / taille, maskable)
                    if c is not None: r += c[0]; g += c[1]; b += c[2]; a += 255
            cnt = n * n
            if a:                                    # couleur prémultipliée → rendue opaque sur les bords
                vis = a // 255
                ligne += bytes((r // vis, g // vis, b // vis, a // cnt))
            else:
                ligne += b"\x00\x00\x00\x00"
        lignes.append(bytes(ligne))
    return png(taille, taille, b"".join(lignes))


def png(w: int, h: int, brut: bytes) -> bytes:
    def bloc(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b""))


ICONES = [("atombox-192.png", 192, False), ("atombox-512.png", 512, False),
          ("atombox-maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)]

if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    for nom, taille, maskable in ICONES:
        with open(os.path.join(SORTIE, nom), "wb") as f: f.write(dessiner(taille, maskable))
        print("  icones/%s (%d px%s)" % (nom, taille, ", maskable" if maskable else ""))
